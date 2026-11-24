from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from core.account_manager import AccountManager
from core.cookie_validator import CookieValidator
from core.logger_manager import LoggerManager


class CookieError(Exception):
    """Raised when cookie loading, parsing, or validation fails."""


class CookieManager:
    """Manages TikTok cookie files for Playwright browser context injection.

    Supports both the legacy file convention (@username-cookie.json) and the
    new DPAPI-encrypted multiaccount system managed by AccountManager.
    """

    COOKIE_PATTERN: str = r"^@(.+)-cookie\.json$"
    REQUIRED_FIELDS: list[str] = ["name", "value", "domain", "path"]

    def __init__(self, cookies_dir: Path, logger: LoggerManager) -> None:
        self._cookies_dir = Path(cookies_dir)
        self._logger = logger

        if not self._cookies_dir.exists():
            self._cookies_dir.mkdir(parents=True, exist_ok=True)
            self._logger.warning(f"Created cookies directory: {self._cookies_dir}")

        self._account_manager = AccountManager(
            data_dir=self._cookies_dir.parent,
            cookies_dir=self._cookies_dir,
        )

    @property
    def account_manager(self) -> AccountManager:
        """Access underlying Multiaccount AccountManager."""
        if self._account_manager._cookies_dir != self._cookies_dir:
            self._account_manager = AccountManager(
                data_dir=self._cookies_dir.parent,
                cookies_dir=self._cookies_dir,
            )
        return self._account_manager

    def list_accounts(self) -> list[str]:
        """Scan both encrypted registry and local files for registered usernames."""
        acc_mgr = self.account_manager
        acc_mgr._migrate_legacy_cookies()
        accounts_set: set[str] = set()

        # 1. From AccountManager
        for acc in acc_mgr.list_accounts():
            if acc.username and not acc.username.startswith("Conta TikTok"):
                accounts_set.add(acc.username.lstrip("@"))

        # 2. From legacy file patterns in cookies_dir
        if self._cookies_dir.exists():
            for file_path in self._cookies_dir.iterdir():
                if file_path.is_file():
                    username = self._extract_username(file_path.name)
                    if username is not None:
                        accounts_set.add(username)

        accounts = sorted(list(accounts_set))
        self._logger.info(f"Found {len(accounts)} account(s): {accounts}")
        return accounts

    def load_cookie(self, username: str) -> list[dict[str, Any]]:
        """Load and normalize cookies for a given username.

        Checks DPAPI encrypted storage first, then legacy file.
        """
        clean_user = username.lstrip("@").strip()
        self._logger.info(f"Loading cookies for @{clean_user}")

        # Check AccountManager
        acc = self._account_manager.get_account_by_username(clean_user)
        if acc:
            try:
                cookies = self._account_manager.load_account_cookies(acc.account_id)
                if cookies and self.validate_cookie(cookies):
                    self._logger.success(f"Loaded {len(cookies)} DPAPI-protected cookie(s) for @{clean_user}")
                    return cookies
            except Exception as exc:
                self._logger.warning(f"Failed loading DPAPI cookies for @{clean_user}: {exc}")

        # Fallback to legacy file
        cookie_path = self._build_cookie_path(clean_user)
        if not cookie_path.exists():
            raise CookieError(f"Cookie file not found for @{clean_user}: {cookie_path}")

        report, normalized = CookieValidator.parse_file(cookie_path)
        if not report.is_valid or not normalized:
            raise CookieError(f"Cookie validation failed for @{clean_user}: {report.summary()}")

        self._logger.success(f"Loaded {len(normalized)} cookie(s) from legacy file for @{clean_user}")
        return normalized

    def validate_cookie(self, cookies: list[dict[str, Any]]) -> bool:
        """Validate required fields: name, value, domain, path."""
        report = CookieValidator.validate_structure(cookies)
        return report.is_valid

    def normalize_cookie(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw cookie list into Playwright format."""
        return CookieValidator.normalize_for_playwright(raw)

    def _extract_username(self, filename: str) -> str | None:
        """Parse username from legacy filename: @<username>-cookie.json."""
        match = re.match(self.COOKIE_PATTERN, filename, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _build_cookie_path(self, username: str) -> Path:
        """Construct full file path for legacy cookie file."""
        return self._cookies_dir / f"@{username}-cookie.json"
