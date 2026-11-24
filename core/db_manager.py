"""SQLite operational persistence manager for TKS Engine Multiaccount system.

Handles database connection, WAL configuration, schema migrations, and transactional
persistence for departments, account assignments, jobs, round-robin cursors, and execution events.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Iterable

from utils.app_paths import get_storage_dir

logger = logging.getLogger("tks.db_manager")

CURRENT_SCHEMA_VERSION = 1

DEFAULT_DEPARTMENTS = [
    {
        "id": "dept_tiktok_01",
        "name": "TikTok 01",
        "employee_id": "01",
        "drawer_id": "drawer-01",
    },
    {
        "id": "dept_tiktok_02",
        "name": "TikTok 02",
        "employee_id": "02",
        "drawer_id": "drawer-02",
    },
    {
        "id": "dept_tiktok_03",
        "name": "TikTok 03",
        "employee_id": "03",
        "drawer_id": "drawer-03",
    },
    {
        "id": "dept_tiktok_04",
        "name": "TikTok 04",
        "employee_id": "04",
        "drawer_id": "drawer-04",
    },
    {
        "id": "dept_tiktok_05",
        "name": "TikTok 05",
        "employee_id": "05",
        "drawer_id": "drawer-05",
    },
    {
        "id": "dept_tiktok_06",
        "name": "TikTok 06",
        "employee_id": "06",
        "drawer_id": "drawer-06",
    },
]


class DatabaseManager:
    """Thread-safe SQLite manager with WAL mode, foreign keys, and migrations."""

    _instance: DatabaseManager | None = None
    _lock = threading.Lock()

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            storage_dir = get_storage_dir()
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = storage_dir / "tks_jobs.db"
        else:
            self._db_path = Path(db_path)
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self.initialize_schema()

    @classmethod
    def get_instance(cls, db_path: Path | str | None = None) -> DatabaseManager:
        with cls._lock:
            if cls._instance is None or (db_path is not None and cls._instance._db_path != Path(db_path)):
                cls._instance = DatabaseManager(db_path)
            return cls._instance

    @property
    def db_path(self) -> Path:
        return self._db_path

    def get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection configured with WAL and FKs."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self._db_path),
                timeout=10.0,
                check_same_thread=False,
                isolation_level=None,  # Autocommit mode by default, manual BEGIN for transactions
            )
            conn.row_factory = sqlite3.Row
            # Enforce mandatory PRAGMAs
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            self._local.conn = conn
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager executing block in an immediate transaction with nesting support."""
        conn = self.get_connection()
        depth = getattr(self._local, "tx_depth", 0)
        self._local.tx_depth = depth + 1

        if depth == 0:
            conn.execute("BEGIN IMMEDIATE;")
        else:
            conn.execute(f"SAVEPOINT sp_{depth};")

        try:
            yield conn
            if depth == 0:
                conn.execute("COMMIT;")
            else:
                conn.execute(f"RELEASE SAVEPOINT sp_{depth};")
        except Exception:
            if depth == 0:
                conn.execute("ROLLBACK;")
            else:
                conn.execute(f"ROLLBACK TO SAVEPOINT sp_{depth};")
            raise
        finally:
            self._local.tx_depth = max(0, getattr(self._local, "tx_depth", 1) - 1)

    def close_connection(self) -> None:
        """Close thread-local connection if open."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None
            self._local.tx_depth = 0

    def initialize_schema(self) -> None:
        """Apply versioned schema migrations up to CURRENT_SCHEMA_VERSION."""
        conn = self.get_connection()
        # Create migrations tracking table if not present
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
        """)

        cur = conn.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cur.fetchone()
        current_version = row[0] if (row and row[0] is not None) else 0

        if current_version < 1:
            self._apply_migration_v1(conn)

        # Backward compatibility for existing databases: ensure file_path column exists
        try:
            cursor = conn.execute("PRAGMA table_info(jobs);")
            columns = [row[1] for row in cursor.fetchall()]
            if "file_path" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN file_path TEXT;")
        except Exception as e:
            logger.debug(f"Column check for file_path: {e}")

    def _apply_migration_v1(self, conn: sqlite3.Connection) -> None:
        """Migration v1: Core tables, indexes, and initial department seed."""
        logger.info("Applying SQLite schema migration v1...")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. departments
        conn.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                employee_id TEXT,
                drawer_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 2. account_assignments
        conn.execute("""
            CREATE TABLE IF NOT EXISTS account_assignments (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'tiktok',
                round_robin_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
                UNIQUE (department_id, account_id, platform)
            );
        """)

        # 3. jobs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                department_id TEXT,
                account_id TEXT,
                drive_file_id TEXT,
                filename TEXT NOT NULL,
                file_path TEXT,
                platform TEXT NOT NULL DEFAULT 'tiktok',
                status TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                schedule_time TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                error_code TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );
        """)

        # Backward compatibility for existing databases: ensure file_path column exists
        try:
            cursor = conn.execute("PRAGMA table_info(jobs);")
            columns = [row[1] for row in cursor.fetchall()]
            if "file_path" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN file_path TEXT;")
        except Exception as e:
            logger.debug(f"Column check for file_path: {e}")

        # 4. round_robin_cursors
        conn.execute("""
            CREATE TABLE IF NOT EXISTS round_robin_cursors (
                id TEXT PRIMARY KEY,
                department_id TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'tiktok',
                last_account_id TEXT,
                next_position INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE (department_id, platform)
            );
        """)

        # 5. execution_events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_events (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                account_id TEXT,
                department_id TEXT,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL
            );
        """)

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_account ON jobs(account_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_dept ON jobs(department_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_drive_file ON jobs(drive_file_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_dept ON account_assignments(department_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_acc ON account_assignments(account_id);")

        # Seed initial departments
        for dept in DEFAULT_DEPARTMENTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO departments (id, name, enabled, employee_id, drawer_id, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?, ?);
                """,
                (dept["id"], dept["name"], dept["employee_id"], dept["drawer_id"], now, now),
            )

        # Mark migration 1 applied
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?);",
            (now,),
        )
        logger.info("SQLite schema migration v1 applied successfully.")

    # ---------------------------------------------------------
    # Helper queries for Departments & Account Assignments
    # ---------------------------------------------------------
    def get_departments(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        conn = self.get_connection()
        query = "SELECT * FROM departments"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY id ASC"
        return [dict(row) for row in conn.execute(query).fetchall()]

    def get_department_by_id_or_name(self, dept_ref: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM departments WHERE id = ? OR LOWER(name) = LOWER(?) LIMIT 1;",
            (dept_ref, dept_ref),
        ).fetchone()
        return dict(row) if row else None

    def set_department_enabled(self, department_id: str, enabled: bool) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.transaction() as conn:
            conn.execute(
                "UPDATE departments SET enabled = ?, updated_at = ? WHERE id = ? OR LOWER(name) = LOWER(?);",
                (1 if enabled else 0, now, department_id, department_id),
            )

    def assign_account_to_department(
        self,
        account_id: str,
        department_id: str,
        platform: str = "tiktok",
        order: int = 0,
        enabled: bool = True,
    ) -> str:
        """Assign or update account assignment in department."""
        dept = self.get_department_by_id_or_name(department_id)
        if not dept:
            raise ValueError(f"Department {department_id} not found")
        resolved_dept_id = dept["id"]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        assignment_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO account_assignments (id, account_id, department_id, platform, round_robin_order, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(department_id, account_id, platform) DO UPDATE SET
                    round_robin_order = excluded.round_robin_order,
                    enabled = excluded.enabled;
                """,
                (assignment_id, account_id, resolved_dept_id, platform, order, 1 if enabled else 0, now),
            )
        return assignment_id

    def unassign_account_from_department(
        self,
        account_id: str,
        department_id: str,
        platform: str = "tiktok",
    ) -> None:
        dept = self.get_department_by_id_or_name(department_id)
        if not dept:
            return
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM account_assignments WHERE account_id = ? AND department_id = ? AND platform = ?;",
                (account_id, dept["id"], platform),
            )

    def get_department_accounts(
        self,
        department_id: str,
        platform: str = "tiktok",
        enabled_only: bool = True,
    ) -> list[dict[str, Any]]:
        dept = self.get_department_by_id_or_name(department_id)
        if not dept:
            return []
        conn = self.get_connection()
        query = """
            SELECT * FROM account_assignments
            WHERE department_id = ? AND platform = ?
        """
        params: list[Any] = [dept["id"], platform]
        if enabled_only:
            query += " AND enabled = 1"
        query += " ORDER BY round_robin_order ASC, created_at ASC;"
        return [dict(row) for row in conn.execute(query, params).fetchall()]

    def set_account_assignment_enabled(
        self,
        account_id: str,
        department_id: str,
        enabled: bool,
        platform: str = "tiktok",
    ) -> None:
        dept = self.get_department_by_id_or_name(department_id)
        if not dept:
            return
        with self.transaction() as conn:
            conn.execute(
                "UPDATE account_assignments SET enabled = ? WHERE account_id = ? AND department_id = ? AND platform = ?;",
                (1 if enabled else 0, account_id, dept["id"], platform),
            )

    def log_execution_event(
        self,
        event_type: str,
        job_id: str | None = None,
        account_id: str | None = None,
        department_id: str | None = None,
        payload: str | None = None,
    ) -> str:
        """Record operational event into execution_events table."""
        event_id = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO execution_events (id, job_id, account_id, department_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (event_id, job_id, account_id, department_id, event_type, payload, now),
            )
        return event_id
