"""Virtual Office event bridge for TKS Engine multiaccount orchestration.

Emits structured, sanitized operational events consumed by TKS Virtual Office 3D,
including character state updates, desk actions, and drawer task signals.
Never exposes cookies, tokens, or credential payloads.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.db_manager import DatabaseManager
from utils.app_paths import get_storage_dir

logger = logging.getLogger("tks.office_bridge")


class OfficeEventBridge:
    """Publishes sanitized events for Virtual Office visualization."""

    _instance: OfficeEventBridge | None = None
    _lock = threading.Lock()

    def __init__(self, storage_dir: Path | None = None, db_manager: DatabaseManager | None = None) -> None:
        self._storage_dir = storage_dir or get_storage_dir()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._events_file = self._storage_dir / "office_events.jsonl"
        self._state_file = self._storage_dir / "multiaccount_state.json"
        self._db = db_manager or DatabaseManager.get_instance()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []

    @classmethod
    def get_instance(cls) -> OfficeEventBridge:
        with cls._lock:
            if cls._instance is None:
                cls._instance = OfficeEventBridge()
            return cls._instance

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)

    def emit(
        self,
        event_name: str,
        department_id: str | None = None,
        account_id: str | None = None,
        username: str | None = None,
        job_id: str | None = None,
        status: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Emit sanitized event to subscribers, disk, and database."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Map department to virtual office drawer / desk metadata
        dept_meta = None
        if department_id:
            dept_meta = self._db.get_department_by_id_or_name(department_id)

        payload: dict[str, Any] = {
            "event": event_name,
            "timestamp": now,
            "department_id": dept_meta["id"] if dept_meta else department_id,
            "department_name": dept_meta["name"] if dept_meta else None,
            "employee_id": dept_meta.get("employee_id") if dept_meta else None,
            "drawer_id": dept_meta.get("drawer_id") if dept_meta else None,
            "account_id": account_id,
            "username": username.lstrip("@") if username else None,
            "job_id": job_id,
            "status": status,
        }

        if extra:
            # Strictly filter out any potential credential keys
            forbidden_keys = {"cookie", "cookies", "password", "token", "auth"}
            clean_extra = {
                k: v for k, v in extra.items()
                if not any(f in k.lower() for f in forbidden_keys)
            }
            payload["details"] = clean_extra

        # 1. Log to SQLite execution_events
        try:
            self._db.log_execution_event(
                event_type=event_name,
                job_id=job_id,
                account_id=account_id,
                department_id=dept_meta["id"] if dept_meta else department_id,
                payload=json.dumps(payload.get("details", {})),
            )
        except Exception as exc:
            logger.debug(f"Could not record event in db: {exc}")

        # 2. Append to office_events.jsonl
        try:
            with open(self._events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug(f"Could not write office event to disk: {exc}")

        # 3. Notify subscribers
        for sub in self._subscribers:
            try:
                sub(payload)
            except Exception as exc:
                logger.debug(f"Subscriber error on {event_name}: {exc}")

        return payload
