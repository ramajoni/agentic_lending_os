"""
Agent prompt loader and templates.

Loads prompt versions from text files in the prompts/ directory to support
prompt versioning and traceability.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent

# Default prompt version files
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt_v1.txt"
USER_PROMPT_FILE = PROMPTS_DIR / "user_prompt_template_v1.txt"


def load_prompt(file_name: str) -> str:
    """Load prompt content from a versioned text file in the prompts directory."""
    path = PROMPTS_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


# Load active prompt versions
SYSTEM_PROMPT = load_prompt("system_prompt_v1.txt")
USER_PROMPT_TEMPLATE = load_prompt("user_prompt_template_v1.txt")


def format_discrepancies(discrepancies: list[dict]) -> str:
    """Format discrepancies into readable text for the prompt."""
    if not discrepancies:
        return "No discrepancies found."

    lines = []
    for i, d in enumerate(discrepancies, 1):
        lines.append(
            f"{i}. **{d.get('discrepancy_type', 'unknown')}** (severity: {d.get('severity', 'unknown')})\n"
            f"   - Field: {d.get('field_name', 'N/A')}\n"
            f"   - Declared: {d.get('declared_value', 'N/A')}\n"
            f"   - Verified: {d.get('verified_value', 'N/A')}\n"
            f"   - Source: {d.get('source', 'N/A')}\n"
            f"   - Details: {d.get('details', 'N/A')}"
        )
    return "\n".join(lines)


def format_tool_history(tool_call_history: list[dict]) -> str:
    """Format tool call history into readable text for the prompt."""
    if not tool_call_history:
        return "No tools called yet — this is the first reasoning step."

    lines = []
    for i, record in enumerate(tool_call_history, 1):
        call = record.get("call", {})
        result = record.get("result", {})
        lines.append(
            f"{i}. **{call.get('tool_name', 'unknown')}**\n"
            f"   - Rationale: {call.get('rationale', 'N/A')}\n"
            f"   - Result: {result.get('result', {})}"
        )
    return "\n".join(lines)


def build_user_prompt(state: dict, prompt_template: str = USER_PROMPT_TEMPLATE) -> str:
    """Build the user prompt from the current investigation state."""
    return prompt_template.format(
        applicant_id=state.get("applicant_id", "unknown"),
        iteration_count=state.get("iteration_count", 0),
        max_iterations=state.get("max_iterations", 5),
        discrepancies_text=format_discrepancies(state.get("discrepancies", [])),
        tool_history_text=format_tool_history(state.get("tool_call_history", [])),
    )


__all__ = [
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "load_prompt",
    "build_user_prompt",
    "format_discrepancies",
    "format_tool_history",
]
