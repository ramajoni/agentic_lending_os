"""
SQLite database session and schema initialization.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from app.config.app_constants import api_config
from app.config.logger import get_logger

log = get_logger(__name__)

_DB_CONNECTION: Optional[sqlite3.Connection] = None


def get_db_path() -> Path:
    """Resolve and ensure the SQLite database directory exists."""
    path = Path(api_config.sqlite_db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_db_connection() -> sqlite3.Connection:
    """Return a thread-safe connection to the SQLite database."""
    global _DB_CONNECTION
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables and indexes if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS applications (
            applicant_id TEXT PRIMARY KEY,
            applicant_name TEXT,
            current_state TEXT NOT NULL,
            application_payload TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dag_results (
            applicant_id TEXT PRIMARY KEY,
            extracted_fields TEXT,
            verification_results TEXT,
            discrepancies TEXT,
            has_discrepancies INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(applicant_id) REFERENCES applications(applicant_id)
        );

        CREATE TABLE IF NOT EXISTS agent_judgments (
            applicant_id TEXT PRIMARY KEY,
            agent_id TEXT,
            decision TEXT,
            confidence REAL,
            rationale TEXT,
            terminal_action TEXT,
            requires_human_approval INTEGER,
            tool_call_trace TEXT,
            guardrail_violations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(applicant_id) REFERENCES applications(applicant_id)
        );

        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            action TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT,
            notes TEXT,
            metadata TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(applicant_id) REFERENCES applications(applicant_id)
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_applications_state ON applications(current_state);
        CREATE INDEX IF NOT EXISTS idx_audit_applicant ON audit_trail(applicant_id);
        CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_trail(actor_id);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
    """)

    # Seed default test personas if users table is empty
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0:
        seed_users = [
            ("cust_001", "customer_rajesh", "customer", "Rajesh Kumar (Borrower)", "rajesh.kumar@example.com"),
            ("rev_l1_001", "reviewer_l1_amit", "l1_reviewer", "Amit Verma (L1 Underwriter)", "amit.verma@bank.internal"),
            ("rev_l2_001", "reviewer_l2_priya", "l2_reviewer", "Priya Sharma (L2 Senior Underwriter)", "priya.sharma@bank.internal"),
            ("mgr_001", "manager_sunil", "manager", "Sunil Mehta (Risk Operations Manager)", "sunil.mehta@bank.internal"),
        ]
        cursor.executemany(
            "INSERT INTO users (user_id, username, role, full_name, email) VALUES (?, ?, ?, ?, ?)",
            seed_users,
        )
        log.info("Default user personas seeded into SQLite database.")

    conn.commit()
    conn.close()
    log.info("SQLite database initialized at %s", get_db_path())

