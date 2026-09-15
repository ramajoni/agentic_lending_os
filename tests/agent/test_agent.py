"""
Unit tests for the LangGraph verification agent.
"""

import pytest
from agent.verification.state import InvestigationState
from agent.verification.graph import build_investigation_graph, compile_graph
from agent.shared.schemas.handoff import VerificationResult


class TestVerificationAgent:
    """Tests for the verification agent graph structure and state."""

    def test_graph_builds_and_compiles(self):
        graph = build_investigation_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_handoff_schema_validation(self):
        handoff = VerificationResult(
            applicant_id="APP-TEST",
            decision="auto_cleared",
            confidence=0.95,
            rationale="Discrepancy resolved through alternate check",
            requires_human_approval=False,
        )
        assert handoff.applicant_id == "APP-TEST"
        assert handoff.decision == "auto_cleared"
