"""
SQLite repository for case persistence, reviewer queues, audit trails, and analytics.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional
from app.utils.db_util import get_db_connection
from app.config.logger import get_logger

log = get_logger(__name__)


class ApplicationRepository:
    """Repository handling all database interactions for loan applications."""

    @staticmethod
    def save_application(
        applicant_id: str,
        applicant_name: str,
        payload: dict,
        initial_state: str = "pending_l1_review",
    ) -> None:
        """Insert or replace an application record."""
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO applications (applicant_id, applicant_name, current_state, application_payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(applicant_id) DO UPDATE SET
                applicant_name = excluded.applicant_name,
                current_state = excluded.current_state,
                application_payload = excluded.application_payload,
                updated_at = excluded.updated_at
            """,
            (applicant_id, applicant_name, initial_state, json.dumps(payload), now, now),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def save_dag_results(
        applicant_id: str,
        extracted: dict,
        verification_results: dict,
        discrepancies: list[dict],
        has_discrepancies: bool,
    ) -> None:
        """Store deterministic DAG findings."""
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO dag_results (applicant_id, extracted_fields, verification_results, discrepancies, has_discrepancies, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(applicant_id) DO UPDATE SET
                extracted_fields = excluded.extracted_fields,
                verification_results = excluded.verification_results,
                discrepancies = excluded.discrepancies,
                has_discrepancies = excluded.has_discrepancies,
                created_at = excluded.created_at
            """,
            (
                applicant_id,
                json.dumps(extracted),
                json.dumps(verification_results),
                json.dumps(discrepancies),
                1 if has_discrepancies else 0,
                now,
            ),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def save_agent_judgment(applicant_id: str, final_state: dict) -> None:
        """Store LangGraph agent investigation findings."""
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO agent_judgments (
                applicant_id, agent_id, decision, confidence, rationale,
                terminal_action, requires_human_approval, tool_call_trace,
                guardrail_violations, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(applicant_id) DO UPDATE SET
                agent_id = excluded.agent_id,
                decision = excluded.decision,
                confidence = excluded.confidence,
                rationale = excluded.rationale,
                terminal_action = excluded.terminal_action,
                requires_human_approval = excluded.requires_human_approval,
                tool_call_trace = excluded.tool_call_trace,
                guardrail_violations = excluded.guardrail_violations,
                created_at = excluded.created_at
            """,
            (
                applicant_id,
                final_state.get("agent_id", "discrepancy_investigation_agent"),
                final_state.get("terminal_action") or "investigated",
                final_state.get("confidence"),
                final_state.get("rationale"),
                final_state.get("terminal_action"),
                1 if final_state.get("requires_human_approval") else 0,
                json.dumps(final_state.get("tool_call_history", [])),
                json.dumps(final_state.get("guardrail_violations", [])),
                now,
            ),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def record_audit(
        applicant_id: str,
        actor_type: str,
        actor_id: str,
        action: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Insert an immutable record in the audit trail."""
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO audit_trail (applicant_id, actor_type, actor_id, action, from_state, to_state, notes, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                applicant_id,
                actor_type,
                actor_id,
                action,
                from_state,
                to_state,
                notes,
                json.dumps(metadata or {}),
                now,
            ),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_application(applicant_id: str) -> Optional[dict]:
        """Fetch raw application record."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications WHERE applicant_id = ?", (applicant_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)

    @staticmethod
    def list_queue(state: str) -> list[dict]:
        """Fetch application queue with DAG and Agent summaries."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                a.applicant_id,
                a.applicant_name,
                a.current_state,
                a.created_at,
                d.has_discrepancies,
                d.discrepancies,
                j.decision as agent_recommendation,
                j.confidence as agent_confidence
            FROM applications a
            LEFT JOIN dag_results d ON a.applicant_id = d.applicant_id
            LEFT JOIN agent_judgments j ON a.applicant_id = j.applicant_id
            WHERE a.current_state = ?
            ORDER BY a.created_at DESC
            """,
            (state,),
        )
        rows = cursor.fetchall()
        conn.close()

        items = []
        for r in rows:
            discrepancies_list = json.loads(r["discrepancies"] or "[]")
            items.append({
                "applicant_id": r["applicant_id"],
                "applicant_name": r["applicant_name"],
                "current_state": r["current_state"],
                "has_discrepancies": bool(r["has_discrepancies"]),
                "discrepancy_count": len(discrepancies_list),
                "agent_recommendation": r["agent_recommendation"],
                "agent_confidence": r["agent_confidence"],
                "created_at": r["created_at"],
            })
        return items

    @staticmethod
    def get_dossier(applicant_id: str) -> Optional[dict]:
        """Fetch complete factual dossier for underwriting review."""
        conn = get_db_connection()
        cursor = conn.cursor()

        # Application
        cursor.execute("SELECT * FROM applications WHERE applicant_id = ?", (applicant_id,))
        app_row = cursor.fetchone()
        if not app_row:
            conn.close()
            return None

        # DAG Results
        cursor.execute("SELECT * FROM dag_results WHERE applicant_id = ?", (applicant_id,))
        dag_row = cursor.fetchone()

        # Agent Judgment
        cursor.execute("SELECT * FROM agent_judgments WHERE applicant_id = ?", (applicant_id,))
        agent_row = cursor.fetchone()

        # Audit history
        cursor.execute("SELECT * FROM audit_trail WHERE applicant_id = ? ORDER BY timestamp ASC", (applicant_id,))
        audit_rows = cursor.fetchall()
        conn.close()

        declared_payload = json.loads(app_row["application_payload"] or "{}")

        dag_facts = None
        if dag_row:
            dag_facts = {
                "extracted_fields": json.loads(dag_row["extracted_fields"] or "{}"),
                "verification_results": json.loads(dag_row["verification_results"] or "{}"),
                "discrepancies": json.loads(dag_row["discrepancies"] or "[]"),
                "has_discrepancies": bool(dag_row["has_discrepancies"]),
            }

        agent_findings = None
        if agent_row:
            agent_findings = {
                "agent_id": agent_row["agent_id"],
                "decision": agent_row["decision"],
                "confidence": agent_row["confidence"],
                "rationale": agent_row["rationale"],
                "terminal_action": agent_row["terminal_action"],
                "requires_human_approval": bool(agent_row["requires_human_approval"]),
                "tool_call_trace": json.loads(agent_row["tool_call_trace"] or "[]"),
                "guardrail_violations": json.loads(agent_row["guardrail_violations"] or "[]"),
            }

        audit_history = []
        for a in audit_rows:
            audit_history.append({
                "id": a["id"],
                "actor_type": a["actor_type"],
                "actor_id": a["actor_id"],
                "action": a["action"],
                "from_state": a["from_state"],
                "to_state": a["to_state"],
                "notes": a["notes"],
                "metadata": json.loads(a["metadata"] or "{}"),
                "timestamp": a["timestamp"],
            })

        return {
            "applicant_id": app_row["applicant_id"],
            "applicant_name": app_row["applicant_name"],
            "current_state": app_row["current_state"],
            "created_at": app_row["created_at"],
            "updated_at": app_row["updated_at"],
            "declared_data": declared_payload,
            "dag_facts": dag_facts,
            "agent_findings": agent_findings,
            "audit_history": audit_history,
        }

    @staticmethod
    def record_l1_decision(
        applicant_id: str,
        reviewer_id: str,
        decision: str,
        notes: str,
    ) -> dict:
        """Apply L1 Reviewer decision and update application state."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT current_state FROM applications WHERE applicant_id = ?", (applicant_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Application '{applicant_id}' not found.")

        prev_state = row["current_state"]
        if prev_state != "pending_l1_review":
            conn.close()
            raise ValueError(f"Application '{applicant_id}' is in state '{prev_state}', not 'pending_l1_review'.")

        new_state = decision  # "approved", "l2_review", or "rejected"
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            "UPDATE applications SET current_state = ?, updated_at = ? WHERE applicant_id = ?",
            (new_state, now, applicant_id),
        )

        cursor.execute(
            """
            INSERT INTO audit_trail (applicant_id, actor_type, actor_id, action, from_state, to_state, notes, timestamp)
            VALUES (?, 'l1_reviewer', ?, 'L1_DECISION', ?, ?, ?, ?)
            """,
            (applicant_id, reviewer_id, prev_state, new_state, notes, now),
        )

        conn.commit()
        conn.close()

        return {
            "application_id": applicant_id,
            "previous_state": prev_state,
            "current_state": new_state,
            "decision": decision,
            "reviewer_id": reviewer_id,
            "notes_or_justification": notes,
            "timestamp": now,
        }

    @staticmethod
    def record_l2_decision(
        applicant_id: str,
        reviewer_id: str,
        decision: str,
        justification: str,
    ) -> dict:
        """Apply L2 Reviewer decision with mandatory justification."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT current_state FROM applications WHERE applicant_id = ?", (applicant_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Application '{applicant_id}' not found.")

        prev_state = row["current_state"]
        if prev_state != "l2_review":
            conn.close()
            raise ValueError(f"Application '{applicant_id}' is in state '{prev_state}', not 'l2_review'.")

        new_state = decision  # "approved" or "rejected"
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            "UPDATE applications SET current_state = ?, updated_at = ? WHERE applicant_id = ?",
            (new_state, now, applicant_id),
        )

        cursor.execute(
            """
            INSERT INTO audit_trail (applicant_id, actor_type, actor_id, action, from_state, to_state, notes, timestamp)
            VALUES (?, 'l2_reviewer', ?, 'L2_DECISION', ?, ?, ?, ?)
            """,
            (applicant_id, reviewer_id, prev_state, new_state, justification, now),
        )

        conn.commit()
        conn.close()

        return {
            "application_id": applicant_id,
            "previous_state": prev_state,
            "current_state": new_state,
            "decision": decision,
            "reviewer_id": reviewer_id,
            "notes_or_justification": justification,
            "timestamp": now,
        }

    @staticmethod
    def get_leaderboard() -> dict:
        """Aggregate operational metrics and reviewer productivity."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM applications")
        total_apps = cursor.fetchone()["count"]

        cursor.execute("SELECT current_state, COUNT(*) as count FROM applications GROUP BY current_state")
        state_distribution = {r["current_state"]: r["count"] for r in cursor.fetchall()}

        cursor.execute("SELECT has_discrepancies, COUNT(*) as count FROM dag_results GROUP BY has_discrepancies")
        discrepancy_counts = {r["has_discrepancies"]: r["count"] for r in cursor.fetchall()}
        clean_count = discrepancy_counts.get(0, 0)
        investigated_count = discrepancy_counts.get(1, 0)

        cursor.execute(
            """
            SELECT 
                actor_id as reviewer_id,
                actor_type as role,
                COUNT(*) as total_reviews,
                SUM(CASE WHEN to_state = 'approved' THEN 1 ELSE 0 END) as approvals,
                SUM(CASE WHEN to_state = 'rejected' THEN 1 ELSE 0 END) as rejections,
                SUM(CASE WHEN to_state = 'l2_review' THEN 1 ELSE 0 END) as escalations
            FROM audit_trail
            WHERE action IN ('L1_DECISION', 'L2_DECISION')
            GROUP BY actor_id, actor_type
            ORDER BY total_reviews DESC
            """
        )
        reviewer_leaderboard = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return {
            "total_applications": total_apps,
            "state_distribution": state_distribution,
            "pipeline_metrics": {
                "clean_cases_passed_by_dag": clean_count,
                "discrepancy_cases_investigated_by_agent": investigated_count,
            },
            "reviewer_leaderboard": reviewer_leaderboard,
        }

    @staticmethod
    def get_case_drilldown(applicant_id: str) -> Optional[dict]:
        """Assemble full chronological step-by-step history of a case."""
        dossier = ApplicationRepository.get_dossier(applicant_id)
        if not dossier:
            return None

        steps = []
        step_num = 1

        steps.append({
            "step_number": step_num,
            "stage": "Customer Application",
            "title": "Application Submitted by Customer",
            "timestamp": dossier["created_at"],
            "actor": "Customer",
            "details": {
                "applicant_name": dossier["applicant_name"],
                "declared_payload": dossier["declared_data"],
            },
        })
        step_num += 1

        dag_facts = dossier.get("dag_facts")
        if dag_facts:
            steps.append({
                "step_number": step_num,
                "stage": "Deterministic DAG",
                "title": "Extraction & External Verification Cross-Check",
                "timestamp": dossier["created_at"],
                "actor": "DAG Verification Engine",
                "details": {
                    "extracted_fields": dag_facts["extracted_fields"],
                    "verification_results": dag_facts["verification_results"],
                    "discrepancies_found": dag_facts["discrepancies"],
                    "has_discrepancies": dag_facts["has_discrepancies"],
                },
            })
            step_num += 1

        agent_findings = dossier.get("agent_findings")
        if agent_findings and agent_findings.get("tool_call_trace"):
            steps.append({
                "step_number": step_num,
                "stage": "Agent Reasoning Loop",
                "title": f"Discrepancy Investigation by {agent_findings['agent_id']}",
                "timestamp": dossier["created_at"],
                "actor": agent_findings["agent_id"],
                "details": {
                    "confidence_score": agent_findings["confidence"],
                    "rationale": agent_findings["rationale"],
                    "terminal_action": agent_findings["terminal_action"],
                    "tool_call_trace": agent_findings["tool_call_trace"],
                    "guardrail_violations": agent_findings["guardrail_violations"],
                },
            })
            step_num += 1

        for a in dossier.get("audit_history", []):
            if a["action"] == "L1_DECISION":
                steps.append({
                    "step_number": step_num,
                    "stage": "L1 Underwriter Review",
                    "title": f"L1 Reviewer Moved Case to '{a['to_state']}'",
                    "timestamp": a["timestamp"],
                    "actor": f"L1 Reviewer ({a['actor_id']})",
                    "details": {
                        "decision": a["to_state"],
                        "reviewer_notes": a["notes"],
                        "previous_state": a["from_state"],
                    },
                })
                step_num += 1
            elif a["action"] == "L2_DECISION":
                steps.append({
                    "step_number": step_num,
                    "stage": "L2 Senior Committee Review",
                    "title": f"L2 Senior Reviewer Decided '{a['to_state']}'",
                    "timestamp": a["timestamp"],
                    "actor": f"L2 Senior Reviewer ({a['actor_id']})",
                    "details": {
                        "decision": a["to_state"],
                        "mandatory_justification": a["notes"],
                        "previous_state": a["from_state"],
                    },
                })
                step_num += 1

        return {
            "applicant_id": dossier["applicant_id"],
            "applicant_name": dossier["applicant_name"],
            "current_state": dossier["current_state"],
            "created_at": dossier["created_at"],
            "updated_at": dossier["updated_at"],
            "total_steps": len(steps),
            "steps": steps,
            "raw_audit_records": dossier.get("audit_history", []),
        }

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[dict]:
        """Fetch user by user_id."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[dict]:
        """Fetch user by username."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_users() -> list[dict]:
        """List all users in the system."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, role, full_name, created_at FROM users ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all_applications() -> list[dict]:
        """List all applications across all states for management view."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                a.applicant_id,
                a.applicant_name,
                a.current_state,
                a.created_at,
                d.has_discrepancies,
                d.discrepancies,
                j.decision as agent_recommendation,
                j.confidence as agent_confidence
            FROM applications a
            LEFT JOIN dag_results d ON a.applicant_id = d.applicant_id
            LEFT JOIN agent_judgments j ON a.applicant_id = j.applicant_id
            ORDER BY a.created_at DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()

        items = []
        for r in rows:
            discrepancies_list = json.loads(r["discrepancies"] or "[]")
            items.append({
                "applicant_id": r["applicant_id"],
                "applicant_name": r["applicant_name"],
                "current_state": r["current_state"],
                "has_discrepancies": bool(r["has_discrepancies"]),
                "discrepancy_count": len(discrepancies_list),
                "agent_recommendation": r["agent_recommendation"],
                "agent_confidence": r["agent_confidence"],
                "created_at": r["created_at"],
            })
        return items

