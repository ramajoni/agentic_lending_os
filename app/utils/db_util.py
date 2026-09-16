"""
SQLite database session, connection utilities, and schema initialization.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from app.constants.app_constants import api_config
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
            applicant_name TEXT NOT NULL,
            current_state TEXT NOT NULL,
            application_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS application_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            reviewer_role TEXT NOT NULL,
            action TEXT NOT NULL,
            justification TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (applicant_id) REFERENCES applications(applicant_id)
        );

        CREATE TABLE IF NOT EXISTS investigation_results (
            applicant_id TEXT PRIMARY KEY,
            decision TEXT NOT NULL,
            confidence REAL,
            terminal_action TEXT,
            rationale TEXT,
            requires_human_approval BOOLEAN,
            discrepancies TEXT,
            tool_call_history TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (applicant_id) REFERENCES applications(applicant_id)
        );

        CREATE TABLE IF NOT EXISTS dag_verifications (
            applicant_id TEXT PRIMARY KEY,
            extracted_data TEXT NOT NULL,
            verified_data TEXT NOT NULL,
            discrepancies TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            FOREIGN KEY (applicant_id) REFERENCES applications(applicant_id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_applications_state ON applications(current_state);
        CREATE INDEX IF NOT EXISTS idx_reviews_applicant ON application_reviews(applicant_id);
        CREATE INDEX IF NOT EXISTS idx_audit_applicant ON audit_log(applicant_id);
    """)

    # Seed mock default users if users table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        log.info("Seeding initial mock users into SQLite database...")
        mock_users = [
            ("USR-CUST-01", "rajesh_customer", "mockpass123", "customer", "Rajesh K. Sharma"),
            ("USR-REV-01", "sarah_reviewer", "mockpass123", "reviewer_l1", "Sarah Jenkins (L1)"),
            ("USR-REV-02", "vikram_reviewer", "mockpass123", "reviewer_l2", "Vikram Patel (L2 Senior)"),
            ("USR-MGR-01", "anita_manager", "mockpass123", "manager", "Anita Roy (Lending Manager)"),
            ("USR-SYS-01", "system_admin", "mockpass123", "admin", "System Administrator"),
        ]
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        cursor.executemany(
            """
            INSERT INTO users (user_id, username, hashed_password, role, full_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(uid, uname, pwd, role, fname, now) for uid, uname, pwd, role, fname in mock_users],
        )

    conn.commit()
    conn.close()
    log.info("SQLite database initialized at %s", get_db_path())

