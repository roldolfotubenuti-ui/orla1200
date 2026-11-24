"""Background worker for read-only session validation in PyQt6."""
from __future__ import annotations

import asyncio
from PyQt6.QtCore import QThread, pyqtSignal

from core.account_manager import AccountManager


class SessionValidationWorker(QThread):
    """Executes read-only validate_tiktok_session on a background thread."""

    validation_finished = pyqtSignal(str, bool, str, str)  # (account_id, is_auth, msg, detected_user)

    def __init__(self, account_manager: AccountManager, account_id: str, headless: bool = True) -> None:
        super().__init__()
        self._manager = account_manager
        self._account_id = account_id
        self._headless = headless

    def run(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            is_auth, msg, detected_user = loop.run_until_complete(
                self._manager.validate_tiktok_session(self._account_id, headless=self._headless)
            )
            loop.close()
            self.validation_finished.emit(self._account_id, is_auth, msg, detected_user or "")
        except Exception as exc:
            self.validation_finished.emit(self._account_id, False, f"Erro: {exc}", "")
