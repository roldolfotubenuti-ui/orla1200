"""RoundRobinRouter for multiaccount distribution in TKS Engine.

Ensures strict 1-to-1 video assignment to accounts within a department using
atomic SQLite transactions, persistent per-department cursor positions, and filtering
for active, enabled, authenticated, and non-busy accounts.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus
from core.db_manager import DatabaseManager

logger = logging.getLogger("tks.round_robin_router")

BUSY_STATUSES = ("RUNNING", "UPLOADING", "PROCESSING", "SUBMITTING")


class RoundRobinRouter:
    """Atomic Round-Robin dispatcher per department and platform."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        account_manager: AccountManager | None = None,
    ) -> None:
        self._db = db_manager or DatabaseManager.get_instance()
        self._account_manager = account_manager or AccountManager()

    def get_eligible_accounts(
        self,
        department_id: str,
        platform: str = "tiktok",
        exclude_busy: bool = True,
    ) -> list[str]:
        """Fetch list of valid, enabled, authenticated account_ids assigned to department."""
        dept = self._db.get_department_by_id_or_name(department_id)
        if not dept or not dept.get("enabled", 1):
            return []

        resolved_dept_id = dept["id"]
        assignments = self._db.get_department_accounts(
            resolved_dept_id,
            platform=platform,
            enabled_only=True,
        )

        eligible_ids: list[str] = []
        conn = self._db.get_connection()

        for assign in assignments:
            acc_id = assign["account_id"]
            acc = self._account_manager.get_account(acc_id)
            if not acc or not acc.enabled:
                continue

            # Check auth status: must not be in expired/invalid/disabled states
            disallowed_statuses = (
                AccountAuthStatus.DISABLED.value,
                AccountAuthStatus.INVALID_SESSION.value,
                AccountAuthStatus.EXPIRED.value,
                AccountAuthStatus.REAUTH_REQUIRED.value,
            )
            if acc.auth_status in disallowed_statuses:
                continue

            # Check if busy in SQLite jobs table
            if exclude_busy:
                placeholders = ",".join("?" for _ in BUSY_STATUSES)
                row = conn.execute(
                    f"SELECT COUNT(*) FROM jobs WHERE account_id = ? AND status IN ({placeholders});",
                    [acc_id, *BUSY_STATUSES],
                ).fetchone()
                if row and row[0] > 0:
                    continue

            eligible_ids.append(acc_id)

        return eligible_ids

    def select_next_account(
        self,
        department_id: str,
        platform: str = "tiktok",
        exclude_busy: bool = True,
    ) -> str | None:
        """Select next account in round-robin order within an atomic SQLite transaction.

        Guarantees that two concurrent calls will never receive the same account
        position in the rotation.
        """
        dept = self._db.get_department_by_id_or_name(department_id)
        if not dept:
            logger.warning(f"Department {department_id} not found for round-robin selection.")
            return None

        resolved_dept_id = dept["id"]

        with self._db.transaction() as conn:
            eligible_ids = self.get_eligible_accounts(
                resolved_dept_id,
                platform=platform,
                exclude_busy=exclude_busy,
            )
            if not eligible_ids:
                logger.info(f"No eligible accounts available for department {dept['name']}")
                return None

            # Retrieve current cursor position
            cursor_row = conn.execute(
                """
                SELECT id, last_account_id, next_position
                FROM round_robin_cursors
                WHERE department_id = ? AND platform = ?;
                """,
                (resolved_dept_id, platform),
            ).fetchone()

            n = len(eligible_ids)
            selected_acc_id: str
            next_idx: int

            if cursor_row is None:
                # No cursor yet: pick index 0
                next_idx = 0
                selected_acc_id = eligible_ids[0]
                cursor_id = str(uuid.uuid4())
                subsequent_pos = (next_idx + 1) % n
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conn.execute(
                    """
                    INSERT INTO round_robin_cursors (id, department_id, platform, last_account_id, next_position, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (cursor_id, resolved_dept_id, platform, selected_acc_id, subsequent_pos, now),
                )
            else:
                last_account_id = cursor_row["last_account_id"]
                saved_position = cursor_row["next_position"]

                if last_account_id in eligible_ids:
                    last_idx = eligible_ids.index(last_account_id)
                    chosen_idx = (last_idx + 1) % n
                else:
                    chosen_idx = saved_position % n

                selected_acc_id = eligible_ids[chosen_idx]
                subsequent_pos = (chosen_idx + 1) % n
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conn.execute(
                    """
                    UPDATE round_robin_cursors
                    SET last_account_id = ?, next_position = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (selected_acc_id, subsequent_pos, now, cursor_row["id"]),
                )

            logger.info(
                f"Round-Robin selected account {selected_acc_id} for department {dept['name']} "
                f"(pool size: {n})"
            )
            return selected_acc_id

    def get_cursor_info(self, department_id: str, platform: str = "tiktok") -> dict[str, Any] | None:
        """Read cursor state without advancing it."""
        dept = self._db.get_department_by_id_or_name(department_id)
        if not dept:
            return None
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM round_robin_cursors WHERE department_id = ? AND platform = ?;",
            (dept["id"], platform),
        ).fetchone()
        return dict(row) if row else None
