"""
LangGraph verification investigation graph.

Defines the StateGraph with 7 nodes and edges:
  init → reasoning → allowlist_gate → tool_execution → loop_check →
  (back to reasoning OR critical_action_gate) → output
"""

from langgraph.graph import StateGraph, END
from agent.verification.state import InvestigationState
from agent.verification.nodes import (
    init_node,
    reasoning_node,
    allowlist_gate,
    tool_execution_node,
    loop_check,
    critical_action_gate_node,
    output_node,
    route_after_loop_check,
)
from app.config.app_constants import agent_config
from app.config.logger import get_logger

log = get_logger(__name__)


def build_investigation_graph() -> StateGraph:
    """Construct the LangGraph StateGraph for discrepancy investigation."""
    graph = StateGraph(InvestigationState)

    graph.add_node("init", init_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("allowlist_gate", allowlist_gate)
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("loop_check", loop_check)
    graph.add_node("critical_action_gate", critical_action_gate_node)
    graph.add_node("output", output_node)

    graph.set_entry_point("init")
    graph.add_edge("init", "reasoning")
    graph.add_edge("reasoning", "allowlist_gate")
    graph.add_edge("allowlist_gate", "tool_execution")
    graph.add_edge("tool_execution", "loop_check")

    graph.add_conditional_edges(
        "loop_check",
        route_after_loop_check,
        {
            "reasoning": "reasoning",
            "critical_action_gate": "critical_action_gate",
        },
    )

    graph.add_edge("critical_action_gate", "output")
    graph.add_edge("output", END)

    return graph


def compile_graph():
    """Build and compile the verification investigation graph."""
    graph = build_investigation_graph()
    return graph.compile()


def run_investigation(
    applicant_id: str,
    discrepancies: list[dict],
    agent_id: str = "discrepancy_investigation_agent",
) -> dict:
    """Run the full verification investigation graph."""
    compiled = compile_graph()

    initial_state: InvestigationState = {
        "applicant_id": applicant_id,
        "agent_id": agent_id,
        "discrepancies": discrepancies,
        "tool_call_history": [],
        "iteration_count": 0,
        "max_iterations": agent_config.max_iterations,
        "confidence": None,
        "terminal_action": None,
        "rationale": None,
        "current_tool_request": None,
        "guardrail_violations": [],
        "requires_human_approval": False,
    }

    log.info("Starting verification graph for applicant %s (%s)", applicant_id, agent_id)
    final_state = compiled.invoke(initial_state)
    log.info("Verification graph completed for applicant %s", applicant_id)

    return final_state
