"""
End-to-end test scenarios — the 3 demo cases from the plan.

These test the full pipeline via the API endpoint.
Each scenario should produce a visibly different tool-call trace.
"""

import pytest
from tests.conftest import (
    SCENARIO_1_PAYLOAD,
    SCENARIO_2_PAYLOAD,
    SCENARIO_3_PAYLOAD,
    INJECTION_PAYLOAD,
    MALFORMED_PAYLOAD,
)


class TestScenario1TrivialCase:
    """Scenario 1: Minor name-spelling variation.

    Expected path: reverify_alternate_source → auto_clear
    Shortest investigation path.
    """

    def test_trivial_case_via_api(self, client):
        response = client.post("/api/v1/verify", json=SCENARIO_1_PAYLOAD)
        assert response.status_code in (200, 202)

        data = response.json()
        assert data["status"] in ("completed", "pending_approval")

        result = data["result"]
        assert result["applicant_id"] == "APP-001"
        assert len(result["discrepancies_found"]) > 0
        assert len(result["tool_call_trace"]) > 0

        # Should have a rationale
        assert result["rationale"] is not None and len(result["rationale"]) > 0

        print(f"\n{'='*60}")
        print(f"SCENARIO 1 — Trivial Case")
        print(f"Decision: {result['decision']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Tool calls: {len(result['tool_call_trace'])}")
        for i, tc in enumerate(result["tool_call_trace"], 1):
            print(f"  {i}. {tc['call']['tool_name']}")
        print(f"Requires human approval: {result['requires_human_approval']}")
        print(f"{'='*60}\n")


class TestScenario2CompoundingWeakSignals:
    """Scenario 2: Minor address mismatch + GST timeout + no fraud hit.

    Expected path: Multiple investigation tools before deciding.
    Should use query_historical_cases since no single signal is conclusive.
    """

    def test_compounding_signals_via_api(self, client):
        response = client.post("/api/v1/verify", json=SCENARIO_2_PAYLOAD)
        assert response.status_code in (200, 202)

        data = response.json()
        result = data["result"]
        assert result["applicant_id"] == "APP-002"
        assert len(result["tool_call_trace"]) > 0

        print(f"\n{'='*60}")
        print(f"SCENARIO 2 — Compounding Weak Signals")
        print(f"Decision: {result['decision']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Tool calls: {len(result['tool_call_trace'])}")
        for i, tc in enumerate(result["tool_call_trace"], 1):
            print(f"  {i}. {tc['call']['tool_name']}")
        print(f"Requires human approval: {result['requires_human_approval']}")
        print(f"{'='*60}\n")


class TestScenario3EscalationForcing:
    """Scenario 3: Income mismatch above materiality + fraud watchlist hit.

    Expected path: Agent should escalate quickly.
    Critical-action gate should mark as pending_human_approval.
    """

    def test_escalation_via_api(self, client):
        response = client.post("/api/v1/verify", json=SCENARIO_3_PAYLOAD)
        assert response.status_code in (200, 202)

        data = response.json()
        result = data["result"]
        assert result["applicant_id"] == "APP-003"

        # Should require human approval
        assert result["requires_human_approval"] is True

        # Should have escalated or be pending
        assert result["decision"] in (
            "escalated_to_human",
            "pending_human_approval",
        )

        print(f"\n{'='*60}")
        print(f"SCENARIO 3 — Escalation-Forcing Case")
        print(f"Decision: {result['decision']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Tool calls: {len(result['tool_call_trace'])}")
        for i, tc in enumerate(result["tool_call_trace"], 1):
            print(f"  {i}. {tc['call']['tool_name']}")
        print(f"Requires human approval: {result['requires_human_approval']}")
        print(f"Guardrail violations: {result['guardrail_violations']}")
        print(f"{'='*60}\n")


class TestGuardrailEnforcement:
    """Test that guardrails actually block bad inputs."""

    def test_injection_blocked(self, client):
        """Guard 2 should block prompt injection."""
        response = client.post("/api/v1/verify", json=INJECTION_PAYLOAD)
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INJECTION_DETECTED"

    def test_sql_injection_blocked(self, client):
        """Guard 2 should block SQL injection in applicant_name."""
        payload = {
            "application": {
                "applicant_id": "APP-003",
                "applicant_name": "Select * from all_tables",
                "pan_number": "ZZZZZ9999Z",
                "aadhaar_number": "999999999999",
                "date_of_birth": "2000-01-01",
                "address": "123 Test St",
                "phone_number": "9999999999",
                "email": "test@test.com",
                "annual_income": 100000000,
                "loan_amount_requested": 50000000,
                "gst_number": "27ABCDE1234F1Z5",
                "documents": [],
                "remarks": "",
            }
        }
        response = client.post("/api/v1/verify", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INJECTION_DETECTED"
        violations = data["details"]["violations"]
        assert any(v["field"] == "applicant_name" for v in violations)

    def test_malformed_input_blocked(self, client):
        """Guard 1 should block malformed payloads."""
        response = client.post("/api/v1/verify", json=MALFORMED_PAYLOAD)
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INPUT_VALIDATION_FAILED"

    def test_health_check(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_duplicate_tool_call_intercepted_by_allowlist_gate(self):
        """Guard 4 in agent graph intercepts attempt to call same tool twice."""
        from agent.verification.nodes import allowlist_gate
        from agent.verification.state import InvestigationState

        state: InvestigationState = {
            "applicant_id": "APP-TEST-DUP",
            "agent_id": "discrepancy_investigation_agent",
            "discrepancies": [{"type": "name_mismatch", "severity": "low"}],
            "tool_call_history": [
                {
                    "call": {
                        "tool_name": "reverify_alternate_source",
                        "arguments": {"field_name": "applicant_name"},
                        "rationale": "Initial reverification",
                    },
                    "result": {"tool_name": "reverify_alternate_source", "success": True},
                }
            ],
            "iteration_count": 1,
            "max_iterations": 5,
            "confidence": 0.80,
            "terminal_action": None,
            "rationale": None,
            "current_tool_request": {
                "action": "reverify_alternate_source",
                "arguments": {"field_name": "applicant_name"},
                "rationale": "Attempting to reverify again with same args",
                "confidence": 0.80,
            },
            "guardrail_violations": [],
            "requires_human_approval": False,
        }

        updates = allowlist_gate(state)

        # Allowlist gate should have blocked the duplicate and forced escalation
        assert len(updates["guardrail_violations"]) >= 1
        assert "Guard 4: Tool 'reverify_alternate_source' has already been called with identical arguments" in updates["guardrail_violations"][0]
        assert updates["current_tool_request"]["action"] == "escalate_to_human"
        assert "Allowlist gate blocked" in updates["current_tool_request"]["rationale"]
