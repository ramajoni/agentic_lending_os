"""
Guard 9 — Confidence-based routing.

Governs when the agent is allowed to stop investigating vs. must
continue or escalate, based on the confidence score.
"""

from app.config.logger import get_logger
from app.config.app_constants import agent_config

log = get_logger(__name__)


class ConfidenceRouting:
    """Routing decisions based on confidence thresholds."""

    CAN_TERMINATE = "can_terminate"
    MUST_CONTINUE = "must_continue"
    MUST_ESCALATE = "must_escalate"


def evaluate_confidence(
    confidence: float | None,
    iteration_count: int,
    max_iterations: int,
) -> str:
    """Determine what the agent should do based on its confidence level.

    Args:
        confidence: Agent's self-reported confidence (0-1), or None.
        iteration_count: How many tool calls have been made.
        max_iterations: Safety cap on tool calls.

    Returns:
        One of ConfidenceRouting.{CAN_TERMINATE, MUST_CONTINUE, MUST_ESCALATE}
    """
    threshold = agent_config.confidence_threshold

    # If at max iterations, must escalate regardless
    if iteration_count >= max_iterations:
        log.warning(
            "Guard 9 — max iterations (%d) reached, forcing escalation",
            max_iterations,
        )
        return ConfidenceRouting.MUST_ESCALATE

    # No confidence reported yet — must continue investigating
    if confidence is None:
        log.info("Guard 9 — no confidence reported yet, must continue")
        return ConfidenceRouting.MUST_CONTINUE

    if confidence >= threshold:
        log.info(
            "Guard 9 PASSED — confidence %.2f >= threshold %.2f, can terminate",
            confidence,
            threshold,
        )
        return ConfidenceRouting.CAN_TERMINATE

    # Below threshold but still has iterations left
    log.info(
        "Guard 9 — confidence %.2f < threshold %.2f, must continue (iteration %d/%d)",
        confidence,
        threshold,
        iteration_count,
        max_iterations,
    )
    return ConfidenceRouting.MUST_CONTINUE
