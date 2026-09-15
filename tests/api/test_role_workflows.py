"""
Unit and integration tests for role-based workflows and SQLite persistence:
- Customer (Apply & Status tracking)
- L1 Reviewer (Queue, Dossier inspection, Decisioning to Approved / L2 Review / Reject)
- L2 Senior Reviewer (Queue, Dossier inspection, Binding Approval / Rejection with mandatory justification)
- Manager (Leaderboard analytics & Chronological case drill-down)
"""

import pytest
from tests.conftest import (
    SCENARIO_1_PAYLOAD,
    SCENARIO_2_PAYLOAD,
    SCENARIO_3_PAYLOAD,
    INJECTION_PAYLOAD,
)
from app.models.application_state import ApplicationState


class TestCustomerFlow:
    """Customer role endpoints."""

    def test_customer_apply_success(self, client):
        response = client.post("/api/v1/customer/apply", json=SCENARIO_1_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        assert data["application_id"] == "APP-001"
        assert data["status"] == ApplicationState.PENDING_L1_REVIEW.value
        assert "queued for underwriting review" in data["message"]

    def test_customer_status_check(self, client):
        # First ensure submitted
        client.post("/api/v1/customer/apply", json=SCENARIO_1_PAYLOAD)

        response = client.get("/api/v1/customer/applications/APP-001/status")
        assert response.status_code == 200

        data = response.json()
        assert data["application_id"] == "APP-001"
        assert data["status"] == ApplicationState.PENDING_L1_REVIEW.value
        assert "under review" in data["message"]

    def test_customer_apply_injection_blocked(self, client):
        response = client.post("/api/v1/customer/apply", json=INJECTION_PAYLOAD)
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INJECTION_DETECTED"

    def test_customer_status_not_found(self, client):
        response = client.get("/api/v1/customer/applications/UNKNOWN-999/status")
        assert response.status_code == 404


class TestL1ReviewerFlow:
    """L1 Reviewer role endpoints."""

    def test_l1_queue_and_dossier(self, client):
        # Submit application
        client.post("/api/v1/customer/apply", json=SCENARIO_1_PAYLOAD)

        # 1. Fetch L1 Queue
        queue_resp = client.get("/api/v1/reviewer/l1/queue")
        assert queue_resp.status_code == 200
        queue = queue_resp.json()
        app_ids = [item["applicant_id"] for item in queue]
        assert "APP-001" in app_ids

        # 2. Fetch Dossier
        dossier_resp = client.get("/api/v1/reviewer/l1/applications/APP-001")
        assert dossier_resp.status_code == 200
        dossier = dossier_resp.json()
        assert dossier["applicant_id"] == "APP-001"
        assert dossier["current_state"] == ApplicationState.PENDING_L1_REVIEW.value
        assert "dag_facts" in dossier
        assert "declared_data" in dossier

    def test_l1_decision_approve(self, client):
        # Apply APP-001
        client.post("/api/v1/customer/apply", json=SCENARIO_1_PAYLOAD)

        # L1 Reviewer approves
        decision_payload = {
            "reviewer_id": "rev_l1_01",
            "decision": "approved",
            "notes": "Name spelling difference is benign and alternate Aadhaar verification matches.",
        }
        resp = client.post("/api/v1/reviewer/l1/applications/APP-001/decision", json=decision_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["previous_state"] == ApplicationState.PENDING_L1_REVIEW.value
        assert data["current_state"] == ApplicationState.APPROVED.value

        # Verify customer status reflects approval
        cust_resp = client.get("/api/v1/customer/applications/APP-001/status")
        assert cust_resp.json()["status"] == ApplicationState.APPROVED.value

    def test_l1_decision_escalate_to_l2(self, client):
        # Apply APP-002 (Scenario 2: compounding weak signals)
        client.post("/api/v1/customer/apply", json=SCENARIO_2_PAYLOAD)

        # L1 Reviewer escalates to L2
        decision_payload = {
            "reviewer_id": "rev_l1_01",
            "decision": "l2_review",
            "notes": "Address mismatch combined with GST timeout needs senior committee sign-off.",
        }
        resp = client.post("/api/v1/reviewer/l1/applications/APP-002/decision", json=decision_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["previous_state"] == ApplicationState.PENDING_L1_REVIEW.value
        assert data["current_state"] == ApplicationState.L2_REVIEW.value

        # Verify case is now in L2 queue
        l2_queue_resp = client.get("/api/v1/reviewer/l2/queue")
        l2_ids = [item["applicant_id"] for item in l2_queue_resp.json()]
        assert "APP-002" in l2_ids

    def test_l1_decision_reject(self, client):
        # Apply APP-003 (Scenario 3: income mismatch + fraud hit)
        client.post("/api/v1/customer/apply", json=SCENARIO_3_PAYLOAD)

        decision_payload = {
            "reviewer_id": "rev_l1_01",
            "decision": "rejected",
            "notes": "Fraud watchlist match confirmed. Immediate rejection.",
        }
        resp = client.post("/api/v1/reviewer/l1/applications/APP-003/decision", json=decision_payload)
        assert resp.status_code == 200
        assert resp.json()["current_state"] == ApplicationState.REJECTED.value


class TestL2ReviewerFlow:
    """L2 Senior Reviewer role endpoints."""

    def test_l2_queue_and_decision_with_justification(self, client):
        # Ensure APP-002 is escalated to L2
        client.post("/api/v1/customer/apply", json=SCENARIO_2_PAYLOAD)
        client.post(
            "/api/v1/reviewer/l1/applications/APP-002/decision",
            json={"reviewer_id": "rev_l1_01", "decision": "l2_review", "notes": "Escalating address issue."},
        )

        # 1. Check L2 Dossier
        dossier_resp = client.get("/api/v1/reviewer/l2/applications/APP-002")
        assert dossier_resp.status_code == 200
        assert dossier_resp.json()["current_state"] == ApplicationState.L2_REVIEW.value

        # 2. Rejection if justification is too short
        short_payload = {
            "reviewer_id": "senior_l2_01",
            "decision": "approved",
            "justification": "ok",  # Less than 10 chars
        }
        bad_resp = client.post("/api/v1/reviewer/l2/applications/APP-002/decision", json=short_payload)
        assert bad_resp.status_code == 422

        # 3. Valid L2 approval with proper justification
        valid_payload = {
            "reviewer_id": "senior_l2_01",
            "decision": "approved",
            "justification": "Verified physical electricity utility bill with applicant. Address variance explained and cleared.",
        }
        good_resp = client.post("/api/v1/reviewer/l2/applications/APP-002/decision", json=valid_payload)
        assert good_resp.status_code == 200
        data = good_resp.json()
        assert data["previous_state"] == ApplicationState.L2_REVIEW.value
        assert data["current_state"] == ApplicationState.APPROVED.value
        assert data["reviewer_id"] == "senior_l2_01"


class TestManagerFlow:
    """Manager role endpoints."""

    def test_manager_leaderboard(self, client):
        resp = client.get("/api/v1/manager/leaderboard")
        assert resp.status_code == 200
        data = resp.json()

        assert "total_applications" in data
        assert "state_distribution" in data
        assert "pipeline_metrics" in data
        assert "reviewer_leaderboard" in data
        assert data["total_applications"] >= 1

    def test_manager_case_drilldown(self, client):
        # Drill down into APP-002
        resp = client.get("/api/v1/manager/cases/APP-002/drilldown")
        assert resp.status_code == 200
        drilldown = resp.json()

        assert drilldown["applicant_id"] == "APP-002"
        assert drilldown["total_steps"] >= 3
        step_titles = [s["title"] for s in drilldown["steps"]]
        assert any("Submitted" in t for t in step_titles)
        assert any("DAG" in s["stage"] or "Extraction" in t for s, t in zip(drilldown["steps"], step_titles))


class TestAuthAndJWT:
    """Mock JWT authentication and persona token issuance."""

    def test_generate_token_for_personas(self, client):
        roles = ["customer", "l1_reviewer", "l2_reviewer", "manager"]
        for r in roles:
            resp = client.post("/api/v1/auth/token", json={"role": r})
            assert resp.status_code == 200
            data = resp.json()
            assert data["role"] == r
            assert len(data["access_token"]) > 20

    def test_auth_me_endpoint(self, client):
        token_resp = client.post("/api/v1/auth/token", json={"username": "reviewer_l1_amit"})
        token = token_resp.json()["access_token"]

        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "reviewer_l1_amit"
        assert me_resp.json()["role"] == "l1_reviewer"

    def test_personas_directory(self, client):
        resp = client.get("/api/v1/auth/personas")
        assert resp.status_code == 200
        personas = resp.json()
        assert len(personas) >= 4
        usernames = [p["username"] for p in personas]
        assert "customer_rajesh" in usernames
        assert "manager_sunil" in usernames


class TestUnifiedResourceWorkflow:
    """Unified Resource-Centric endpoints (/applications, /analytics) with JWT role projection."""

    @pytest.fixture
    def tokens(self, client):
        """Helper fixture generating tokens for all 4 roles."""
        return {
            "customer": client.post("/api/v1/auth/token", json={"role": "customer"}).json()["access_token"],
            "l1": client.post("/api/v1/auth/token", json={"role": "l1_reviewer"}).json()["access_token"],
            "l2": client.post("/api/v1/auth/token", json={"role": "l2_reviewer"}).json()["access_token"],
            "manager": client.post("/api/v1/auth/token", json={"role": "manager"}).json()["access_token"],
        }

    def test_unified_application_submission(self, client, tokens):
        # 1. Non-customer cannot submit application (403 Forbidden)
        forbidden_resp = client.post(
            "/api/v1/applications",
            json=SCENARIO_1_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['l1']}"},
        )
        assert forbidden_resp.status_code == 403

        # 2. Customer submits application (200 OK)
        resp = client.post(
            "/api/v1/applications",
            json=SCENARIO_1_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == ApplicationState.PENDING_L1_REVIEW.value

    def test_unified_queue_listing_by_role(self, client, tokens):
        # Submit test application APP-001
        client.post(
            "/api/v1/applications",
            json=SCENARIO_1_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        )

        # L1 Reviewer lists queue -> receives pending_l1_review queue
        l1_list = client.get("/api/v1/applications", headers={"Authorization": f"Bearer {tokens['l1']}"})
        assert l1_list.status_code == 200
        l1_apps = l1_list.json()
        assert any(a["applicant_id"] == "APP-001" for a in l1_apps)

        # Customer lists queue -> receives customer view
        cust_list = client.get("/api/v1/applications", headers={"Authorization": f"Bearer {tokens['customer']}"})
        assert cust_list.status_code == 200
        assert any(a["application_id"] == "APP-001" for a in cust_list.json())

    def test_unified_detail_view_projection(self, client, tokens):
        # Ensure APP-001 submitted
        client.post(
            "/api/v1/applications",
            json=SCENARIO_1_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        )

        # 1. Customer view: Sanitized, no agent findings or DAG facts exposed
        cust_resp = client.get(
            "/api/v1/applications/APP-001",
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        )
        assert cust_resp.status_code == 200
        cust_data = cust_resp.json()
        assert "application_id" in cust_data
        assert "status" in cust_data
        assert "dag_facts" not in cust_data
        assert "agent_findings" not in cust_data

        # 2. Reviewer view: Complete factual dossier checked by agent
        l1_resp = client.get(
            "/api/v1/applications/APP-001",
            headers={"Authorization": f"Bearer {tokens['l1']}"},
        )
        assert l1_resp.status_code == 200
        l1_data = l1_resp.json()
        assert "dag_facts" in l1_data
        assert "declared_data" in l1_data

        # 3. Manager view: Dossier + Chronological Drill-Down
        mgr_resp = client.get(
            "/api/v1/applications/APP-001",
            headers={"Authorization": f"Bearer {tokens['manager']}"},
        )
        assert mgr_resp.status_code == 200
        mgr_data = mgr_resp.json()
        assert "dossier" in mgr_data
        assert "drilldown" in mgr_data
        assert mgr_data["drilldown"]["total_steps"] >= 2

    def test_unified_decision_gate(self, client, tokens):
        # Submit APP-002
        client.post(
            "/api/v1/applications",
            json=SCENARIO_2_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        )

        # 1. Customer cannot submit decision (403 Forbidden)
        cust_dec = client.post(
            "/api/v1/applications/APP-002/decision",
            json={"decision": "approved"},
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        )
        assert cust_dec.status_code == 403

        # 2. L1 Reviewer escalates to L2
        l1_dec = client.post(
            "/api/v1/applications/APP-002/decision",
            json={"decision": "l2_review", "notes": "Escalating address mismatch to senior review."},
            headers={"Authorization": f"Bearer {tokens['l1']}"},
        )
        assert l1_dec.status_code == 200
        assert l1_dec.json()["current_state"] == ApplicationState.L2_REVIEW.value

        # 3. L2 Reviewer approves with mandatory justification
        l2_dec = client.post(
            "/api/v1/applications/APP-002/decision",
            json={
                "decision": "approved",
                "justification": "Verified physical electricity bill with municipal council. Cleared.",
            },
            headers={"Authorization": f"Bearer {tokens['l2']}"},
        )
        assert l2_dec.status_code == 200
        assert l2_dec.json()["current_state"] == ApplicationState.APPROVED.value

    def test_manager_analytics_leaderboard_rbac(self, client, tokens):
        # Customer forbidden on analytics
        assert client.get(
            "/api/v1/analytics/leaderboard",
            headers={"Authorization": f"Bearer {tokens['customer']}"},
        ).status_code == 403

        # L1 Reviewer forbidden on analytics
        assert client.get(
            "/api/v1/analytics/leaderboard",
            headers={"Authorization": f"Bearer {tokens['l1']}"},
        ).status_code == 403

        # Manager authorized
        mgr_resp = client.get(
            "/api/v1/analytics/leaderboard",
            headers={"Authorization": f"Bearer {tokens['manager']}"},
        )
        assert mgr_resp.status_code == 200
        data = mgr_resp.json()
        assert "total_applications" in data
        assert "reviewer_leaderboard" in data

