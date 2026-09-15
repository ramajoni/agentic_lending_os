"""
Tool: escalate_to_human

Hands off the case to an underwriter with the full reasoning trail.
TERMINAL — ends the agent's investigation.
"""

from app.config.logger import get_logger

log = get_logger(__name__)


def escalate_to_human(
    reason: str,
    priority: str = "normal",
    recommended_reviewer: str = "senior_underwriter",
    applicant_id: str = "",
) -> dict:
    """Escalate the case to a human underwriter.

    Args:
        reason: Why this case needs human review.
        priority: Priority level (low, normal, high, urgent).
        recommended_reviewer: Suggested reviewer role.
        applicant_id: For logging context.

    Returns:
        Dict confirming the escalation.
    """
    log.info(
        "Tool [escalate_to_human] — priority='%s', applicant='%s'",
        priority, applicant_id,
    )

    return {
        "tool": "escalate_to_human",
        "is_terminal": True,
        "status": "escalation_created",
        "reason": reason,
        "priority": priority,
        "recommended_reviewer": recommended_reviewer,
        "message": f"Case escalated to {recommended_reviewer} with priority '{priority}'.",
        "applicant_id": applicant_id,
    }
