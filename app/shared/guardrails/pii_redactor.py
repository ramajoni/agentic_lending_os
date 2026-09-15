"""
Guard 3 — PII detection and redaction using Microsoft Presidio.

Uses Microsoft Presidio (AnalyzerEngine & AnonymizerEngine) with custom
recognizers for Indian financial entities (PAN, Aadhaar, Indian mobile phones)
alongside standard email and phone detection.
Provides fallback to regex matching if Presidio is disabled or unavailable.
"""

import os
import re
import copy
from typing import Optional
from app.config.logger import get_logger
from app.config.app_constants import guardrail_config

# Disable tldextract network downloads in sandboxed or offline environments
os.environ.setdefault("TLDEXTRACT_CACHE", "/tmp/tldextract")

log = get_logger(__name__)


# ── Presidio Service ─────────────────────────────────────────────────────────

class PresidioService:
    """Singleton wrapper around Microsoft Presidio Analyzer and Anonymizer."""

    _instance: Optional["PresidioService"] = None

    def __init__(self):
        from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig

        # Use pre-installed en_core_web_sm model
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = provider.create_engine()
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

        # Custom Indian Financial Entity Recognizers
        pan_pattern = Pattern(
            name="pan_pattern",
            regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
            score=0.95,
        )
        pan_recognizer = PatternRecognizer(
            supported_entity="PAN",
            patterns=[pan_pattern],
        )
        self.analyzer.registry.add_recognizer(pan_recognizer)

        aadhaar_pattern = Pattern(
            name="aadhaar_pattern",
            regex=r"\b\d{4}\s?\d{4}\s?\d{4}\b",
            score=0.95,
        )
        aadhaar_recognizer = PatternRecognizer(
            supported_entity="AADHAAR",
            patterns=[aadhaar_pattern],
        )
        self.analyzer.registry.add_recognizer(aadhaar_recognizer)

        india_phone_pattern = Pattern(
            name="india_phone_pattern",
            regex=r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b",
            score=0.85,
        )
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[india_phone_pattern],
        )
        self.analyzer.registry.add_recognizer(phone_recognizer)

        self.anonymizer = AnonymizerEngine()

        # Custom Masking Operators
        def _mask_pan(val: str) -> str:
            val = val.strip()
            if len(val) >= 10:
                return val[:2] + "XXX" + val[5:8] + val[-1]
            return val[:2] + "XXX"

        def _mask_aadhaar(val: str) -> str:
            digits = re.sub(r"\s", "", val)
            return "XXXX XXXX " + digits[-4:]

        def _mask_phone(val: str) -> str:
            return re.sub(r"\d", "X", val[:-4]) + val[-4:]

        def _mask_email(val: str) -> str:
            if "@" in val:
                parts = val.split("@")
                return parts[0][0] + "***@" + parts[1]
            return val

        self.operators = {
            "PAN": OperatorConfig("custom", {"lambda": _mask_pan}),
            "AADHAAR": OperatorConfig("custom", {"lambda": _mask_aadhaar}),
            "PHONE_NUMBER": OperatorConfig("custom", {"lambda": _mask_phone}),
            "EMAIL_ADDRESS": OperatorConfig("custom", {"lambda": _mask_email}),
        }
        self.target_entities = ["PAN", "AADHAAR", "PHONE_NUMBER", "EMAIL_ADDRESS"]
        log.info("Microsoft Presidio PII engines initialized successfully.")

    @classmethod
    def get_instance(cls) -> Optional["PresidioService"]:
        if not guardrail_config.presidio_enabled:
            return None
        if cls._instance is None:
            try:
                cls._instance = cls()
            except Exception as e:
                log.warning("Failed to initialize Microsoft Presidio: %s. Falling back to regex.", e)
                return None
        return cls._instance

    def redact(self, text: str) -> str:
        results = self.analyzer.analyze(
            text=text,
            entities=self.target_entities,
            language="en",
            score_threshold=0.5,
        )
        if not results:
            return text
        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=self.operators,
        )
        return anonymized.text


# ── Regex Fallback Patterns ──────────────────────────────────────────────────

_FALLBACK_PATTERNS: dict[str, tuple[re.Pattern, object]] = {
    "pan": (
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
        lambda m: m.group()[:2] + "XXX" + m.group()[5:8] + m.group()[-1],
    ),
    "aadhaar": (
        re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
        lambda m: "XXXX XXXX " + re.sub(r"\s", "", m.group())[-4:],
    ),
    "phone": (
        re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b"),
        lambda m: re.sub(r"\d", "X", m.group()[:-4]) + m.group()[-4:],
    ),
    "email": (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        lambda m: m.group()[0] + "***@" + m.group().split("@")[1],
    ),
}

# Fields known to contain PII that should always be redacted
_PII_FIELDS = {
    "pan_number", "aadhaar_number", "phone_number", "email",
    "name_from_pan", "name_from_aadhaar",
}


def _regex_redact(text: str) -> str:
    """Fallback regex-based redaction."""
    result = text
    for _, (pattern, replacer) in _FALLBACK_PATTERNS.items():
        result = pattern.sub(replacer, result)
    return result


def redact_text(text: str) -> str:
    """Redact all PII patterns in a text string using Microsoft Presidio (or regex fallback).

    Args:
        text: Raw text that may contain PII.

    Returns:
        Text with PII values masked.
    """
    if not text or not guardrail_config.pii_redaction_enabled:
        return text

    if guardrail_config.presidio_enabled:
        presidio = PresidioService.get_instance()
        if presidio:
            try:
                return presidio.redact(text)
            except Exception as e:
                log.warning("Presidio redaction error: %s. Using regex fallback.", e)

    return _regex_redact(text)


def redact_value(value: str, field_name: str) -> str:
    """Redact a specific field value based on field name or pattern matching.

    For known PII fields, redacts aggressively.
    For other fields, preserves value.
    """
    if not guardrail_config.pii_redaction_enabled:
        return value

    if not isinstance(value, str):
        return value

    if field_name in _PII_FIELDS:
        return redact_text(value)

    return value


def redact_dict(data: dict, deep: bool = True) -> dict:
    """Redact PII from all string values in a dictionary.

    Args:
        data: Dictionary potentially containing PII in its values.
        deep: If True, recursively redact nested dicts and lists.

    Returns:
        A new dict with PII values masked.
    """
    if not guardrail_config.pii_redaction_enabled:
        return data

    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = redact_value(value, key)
        elif isinstance(value, dict) and deep:
            result[key] = redact_dict(value, deep=True)
        elif isinstance(value, list) and deep:
            result[key] = [
                redact_dict(item, deep=True) if isinstance(item, dict)
                else redact_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def redact_for_logging(data: dict) -> dict:
    """Create a redacted copy of data suitable for logging.

    Makes a deep copy to avoid mutating the original.
    """
    if not guardrail_config.pii_redaction_enabled:
        return data

    redacted = redact_dict(copy.deepcopy(data))
    log.debug("Guard 3 — PII redaction applied for logging")
    return redacted


def redact_for_response(data: dict) -> dict:
    """Redact PII from the final API response payload.

    This is the last line of defense before data leaves the system.
    """
    if not guardrail_config.pii_redaction_enabled:
        return data

    redacted = redact_dict(copy.deepcopy(data))
    log.info("Guard 3 APPLIED — PII redacted from response")
    return redacted
