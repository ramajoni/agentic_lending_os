"""
Shared LLM client factory and response parsing.
"""

import json
import re
from langchain_groq import ChatGroq
from app.config.app_constants import agent_config
from app.config.logger import get_logger

log = get_logger(__name__)


def get_llm(temperature: float = 0.1, max_tokens: int = 1024) -> ChatGroq:
    """Create a configured ChatGroq instance."""
    return ChatGroq(
        api_key=agent_config.groq_api_key,
        model_name=agent_config.groq_model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def parse_structured_decision(content: str) -> dict:
    """Parse raw LLM response text into a structured dictionary."""
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if json_match:
        content = json_match.group(1).strip()

    if not content.startswith("{"):
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        log.error("Failed to parse LLM response as JSON: %s", content[:200])
        return {
            "action": "escalate_to_human",
            "arguments": {
                "reason": "Agent failed to produce structured output — escalating for safety",
                "priority": "high",
            },
            "rationale": f"LLM output was not valid JSON. Raw output: {content[:200]}",
            "confidence": 0.0,
        }
