"""
Agent reasoning module.

The LLM call that drives the agent's decision-making.
Uses ChatGroq with structured output parsing.
"""

import json
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from agent.verification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.config.app_constants import agent_config
from app.config.logger import get_logger

log = get_logger(__name__)


def _get_llm() -> ChatGroq:
    """Create a ChatGroq instance from config."""
    return ChatGroq(
        api_key=agent_config.groq_api_key,
        model_name=agent_config.groq_model_name,
        temperature=0.1,  # Low temperature for consistent reasoning
        max_tokens=1024,
    )


def _parse_llm_response(content: str) -> dict:
    """Parse the LLM response into a structured decision.

    Extracts JSON from the response, handling cases where the LLM
    wraps it in markdown code blocks.
    """
    # Try to extract JSON from code blocks first
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if json_match:
        content = json_match.group(1).strip()

    # Also try to find raw JSON objects
    if not content.startswith("{"):
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        log.error("Failed to parse LLM response as JSON: %s", content[:200])
        # Fallback: return a safe escalation
        parsed = {
            "action": "escalate_to_human",
            "arguments": {
                "reason": "Agent failed to produce structured output — escalating for safety",
                "priority": "high",
            },
            "rationale": f"LLM output was not valid JSON. Raw output: {content[:200]}",
            "confidence": 0.0,
        }

    # Validate required fields
    if "action" not in parsed:
        parsed["action"] = "escalate_to_human"
    if "arguments" not in parsed:
        parsed["arguments"] = {}
    if "rationale" not in parsed:
        parsed["rationale"] = "No rationale provided"
    if "confidence" not in parsed:
        parsed["confidence"] = None

    # Clamp confidence to valid range
    if parsed["confidence"] is not None:
        try:
            parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))
        except (ValueError, TypeError):
            parsed["confidence"] = None

    return parsed


def invoke_reasoning(state: dict) -> dict:
    """Invoke the LLM to reason about the next action.

    Args:
        state: Current InvestigationState dict.

    Returns:
        Dict with: action, arguments, rationale, confidence.
    """
    log.info(
        "Reasoning node — invoking LLM (iteration %d/%d) for applicant %s",
        state.get("iteration_count", 0),
        state.get("max_iterations", 5),
        state.get("applicant_id", "unknown"),
    )

    llm = _get_llm()
    user_prompt = build_user_prompt(state)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content
        log.debug("LLM raw response: %s", content[:500])
    except Exception as e:
        log.error("LLM invocation failed: %s", e)
        # Safe fallback on LLM failure
        return {
            "action": "escalate_to_human",
            "arguments": {
                "reason": f"LLM invocation failed: {str(e)}",
                "priority": "high",
            },
            "rationale": f"LLM call failed with error: {str(e)} — escalating for safety",
            "confidence": 0.0,
        }

    decision = _parse_llm_response(content)
    log.info(
        "Reasoning node — decision: action='%s', confidence=%s",
        decision["action"],
        decision["confidence"],
    )

    return decision
