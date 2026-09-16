"""
Guard 2 — Prompt-injection detection.

Scans extracted free-text fields (name, address, remarks) for:
1. SQL injection, command execution, and prompt-injection patterns (fast local regex).
2. Semantic prompt injection & jailbreak detection using Meta's Llama-Prompt-Guard-2-22M via Hugging Face.
"""

import re
from app.config.logger import get_logger
from app.constants.app_constants import guardrail_config

log = get_logger(__name__)


# ── Injection patterns (case-insensitive) ────────────────────────────────────

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        # Direct instruction overrides
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|context)",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"forget\s+(everything|all|your\s+instructions)",
        # Role/system hijacking
        r"you\s+are\s+now\s+a",
        r"act\s+as\s+(a|an|the)",
        r"system\s*:\s*",
        r"<\s*system\s*>",
        r"\[\s*INST\s*\]",
        r"\[\s*SYS(TEM)?\s*\]",
        # Template/delimiter injection
        r"\{\{.*\}\}",
        r"<\|.*\|>",
        r"###\s*(instruction|system|user|assistant)",
        # Data exfiltration attempts
        r"(print|output|reveal|show|display)\s+(your|the|all)\s+(instructions?|prompts?|rules?|system)",
        r"what\s+(are|were)\s+your\s+(instructions?|rules?|prompts?)",
        # Code execution attempts
        r"(exec|eval|import|__\w+__)\s*\(",
        r"os\.(system|popen|exec)",
        # SQL injection attempts
        r"\bselect\s+(\*|[\w\s,\(\)]+?)\s+from\s+[a-zA-Z_#]",
        r"\binsert\s+into\s+[a-zA-Z_#]",
        r"\bupdate\s+[a-zA-Z_#\.]+\s+set\s+",
        r"\bdelete\s+from\s+[a-zA-Z_#]",
        r"\bdrop\s+(table|database|view|index|procedure|trigger)\b",
        r"\btruncate\s+(table\s+)?[a-zA-Z_#]",
        r"\balter\s+table\b",
        r"\bunion\s+(all\s+)?select\b",
        r"\bexec(ute)?\s+(immediate|sp_|\w+)",
        r"'\s*(or|and)\s*'\d+'\s*=\s*'\d+",
        r"'\s*(or|and)\s*\d+\s*=\s*\d+",
        r"(\bor\b\s+\d+\s*=\s*\d+)",
        r"(\band\b\s+\d+\s*=\s*\d+)",
        r"'\s*;\s*--",
        r";\s*--",
        r"--\s*$",
        r"/\*.*?\*/",
        r"\b(information_schema|all_tables|sysobjects|sys\.tables)\b",
        r"\b(sleep|benchmark)\s*\(\s*\d+\s*\)",
        r"\bwaitfor\s+delay\s+",
    ]
]

# ── Fields to scan ───────────────────────────────────────────────────────────

_SCANNABLE_FIELDS = [
    "applicant_id",
    "applicant_name",
    "address",
    "remarks",
    "email",
    "gst_business_name",
    "gst_business_address",
]


class InjectionDetectedError(Exception):
    """Raised when a prompt-injection pattern or jailbreak is detected."""

    def __init__(self, field: str, pattern: str, value: str):
        self.field = field
        self.pattern = pattern
        self.value_snippet = value[:100]
        super().__init__(
            f"Injection detected in field '{field}': matched pattern '{pattern}'"
        )


def check_prompt_guard(text: str) -> tuple[bool, str | None]:
    """Evaluate text using meta-llama/Llama-Prompt-Guard-2-22M via Hugging Face.

    Returns:
        (is_clean, reason_or_None)
    """
    if not guardrail_config.prompt_guard_enabled:
        return True, None

    hf_token = guardrail_config.hf_token
    if not hf_token or not hf_token.strip():
        return True, None

    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(
            token=hf_token.strip(),
            timeout=5.0,
        )
        results = client.text_classification(
            text=text,
            model=guardrail_config.prompt_guard_model,
        )

        malicious_labels = {"MALICIOUS", "LABEL_1", "INJECTION", "JAILBREAK"}
        threshold = guardrail_config.prompt_guard_threshold

        for pred in results:
            label_str = getattr(pred, "label", "").upper()
            score = float(getattr(pred, "score", 0.0))
            if label_str in malicious_labels and score >= threshold:
                reason = f"Prompt Guard detected '{label_str}' (confidence: {score:.2f}) with model '{guardrail_config.prompt_guard_model}'"
                log.warning("Guard 2 BLOCKED by Prompt Guard: %s", reason)
                return False, reason
        return True, None

    except Exception as e:
        log.warning(
            "Llama Prompt Guard API call failed: %s. Falling back to local heuristics.",
            e,
        )
        return True, None


def scan_text(text: str) -> tuple[bool, str | None]:
    """Scan a single text value for injection patterns."""
    if not text:
        return True, None

    # Step 1: Fast local regex checks
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, pattern.pattern

    # Step 2: Hugging Face Llama-Prompt-Guard-2-22M check
    is_clean, reason = check_prompt_guard(text)
    if not is_clean:
        return False, reason

    return True, None


def scan_fields(data: dict, field_names: list[str] | None = None) -> list[dict]:
    """Scan specified fields in a dict for injection patterns."""
    if not guardrail_config.injection_scan_enabled:
        log.info("Guard 2 SKIPPED — injection scan disabled by config")
        return []

    if field_names:
        fields = field_names
    else:
        fields = list(dict.fromkeys(_SCANNABLE_FIELDS + [k for k, v in data.items() if isinstance(v, str)]))
    violations = []

    for field in fields:
        value = data.get(field, "")
        if not isinstance(value, str):
            continue
        is_clean, pattern = scan_text(value)
        if not is_clean:
            violations.append({
                "field": field,
                "pattern": pattern,
                "snippet": value[:100],
            })

    if violations:
        log.warning(
            "Guard 2 BLOCKED — injection detected in %d field(s): %s",
            len(violations),
            [v["field"] for v in violations],
        )
    else:
        log.info("Guard 2 PASSED — no injection patterns detected")

    return violations


def assert_no_injection(data: dict, field_names: list[str] | None = None) -> None:
    """Scan fields and raise if any injection is found."""
    violations = scan_fields(data, field_names)
    if violations:
        v = violations[0]
        raise InjectionDetectedError(v["field"], v["pattern"], v["snippet"])

