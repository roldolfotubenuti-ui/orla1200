"""Account manager service for TKS Engine multiaccount management.

Handles import, DPAPI encrypted persistence, lifecycle state management,
and read-only Playwright session validation for TikTok accounts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.account_model import AccountAuthStatus, AccountRecord
from core.cookie_validator import CookieValidationReport, CookieValidator
from core.dpapi_crypto import load_encrypted_json, save_encrypted_json
from utils.app_paths import get_cookies_dir, get_user_data_dir

logger = logging.getLogger("tks.account_manager")


class AccountManager:
    """Central manager for Multiaccount TikTok profiles in TKS Engine."""

    DEPARTMENTS: list[str] = [
        "Instagram",
        "Mercado Livre",
        "Shorts",
        "TikTok",
        "TikTok Shop",
        "YouTube",
    ]

    def __init__(self, data_dir: Path | None = None, cookies_dir: Path | None = None) -> None:
        self._data_dir = data_dir or get_user_data_dir()
        self._cookies_dir = cookies_dir or (self._data_dir / "cookies")
        self._cookies_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self._data_dir / "accounts.json"
        self._accounts: dict[str, AccountRecord] = {}
        self._load_registry()
        self._migrate_legacy_cookies()

    def _load_registry(self) -> None:
        """Load registered accounts from accounts.json registry."""
        if not self._registry_path.exists():
            self._accounts = {}
            return

        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                self._accounts = {
                    item["account_id"]: AccountRecord.from_dict(item)
                    for item in raw
                    if isinstance(item, dict) and "account_id" in item
                }
            elif isinstance(raw, dict):
                self._accounts = {
                    k: AccountRecord.from_dict(v)
                    for k, v in raw.items()
                    if isinstance(v, dict)
                }
        except Exception as exc:
            logger.error(f"Failed to read accounts registry {self._registry_path}: {exc}")
            self._accounts = {}

    def _save_registry(self) -> None:
        """Atomically persist accounts registry to disk."""
        try:
            self._registry_path.parent.mkdir(parents=True, exist_ok=True)
            data = [acc.to_dict() for acc in self._accounts.values()]
            temp_path = self._registry_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self._registry_path)
        except Exception as exc:
            logger.error(f"Failed to persist accounts registry: {exc}")

    def _migrate_legacy_cookies(self) -> None:
        """Scan cookies directory for legacy @username-cookie.json and register if missing."""
        if not self._cookies_dir.exists():
            return

        existing_usernames = {
            acc.username.lstrip("@").lower()
            for acc in self._accounts.values()
            if acc.username
        }

        changed = False
        for p in self._cookies_dir.glob("@*-cookie.json"):
            m = re.match(r"^@(.+)-cookie\.json$", p.name)
            if not m:
                continue
            username = m.group(1).lstrip("@")
            if username.lower() in existing_usernames:
                continue

            try:
                report, normalized = CookieValidator.parse_file(p)
                if not report.is_valid:
                    continue

                acc_id = str(uuid.uuid4())
                enc_file = f"{acc_id}.enc"
                enc_path = self._cookies_dir / enc_file
                save_encrypted_json(enc_path, normalized, description=f"TikTok @{username}")

                record = AccountRecord(
                    account_id=acc_id,
                    username=username,
                    platform="tiktok",
                    cookie_file=enc_file,
                    department_id="TikTok",
                    auth_status=AccountAuthStatus.STRUCTURALLY_VALID.value,
                    enabled=True,
                    cookie_count=len(normalized),
                    display_title=f"@{username}",
                )
                self._accounts[acc_id] = record
                existing_usernames.add(username.lower())
                changed = True
            except Exception as exc:
                logger.warning(f"Could not migrate legacy cookie {p.name}: {exc}")

        if changed:
            self._save_registry()

    def list_accounts(self) -> list[AccountRecord]:
        """Return all registered accounts ordered by import date."""
        return list(self._accounts.values())

    def get_account(self, account_id: str) -> AccountRecord | None:
        """Fetch account record by UUID."""
        return self._accounts.get(account_id)

    def get_account_by_username(self, username: str) -> AccountRecord | None:
        """Find account by username."""
        clean = username.lstrip("@").lower()
        for acc in self._accounts.values():
            if acc.username and acc.username.lstrip("@").lower() == clean:
                return acc
        return None

    def load_account_cookies(self, account_id: str) -> list[dict[str, Any]]:
        """Retrieve and decrypt normalized Playwright cookies for an account."""
        acc = self.get_account(account_id)
        if not acc:
            raise ValueError(f"Account {account_id} not found")

        enc_path = self._cookies_dir / acc.cookie_file
        if not enc_path.exists():
            # Check fallback legacy path
            if acc.username:
                legacy_path = self._cookies_dir / f"@{acc.username}-cookie.json"
                if legacy_path.exists():
                    _, normalized = CookieValidator.parse_file(legacy_path)
                    return normalized
            raise FileNotFoundError(f"Credential file not found for account {acc.display_name}")

        return load_encrypted_json(enc_path)

    def import_cookie_files(
        self,
        file_paths: list[Path | str],
    ) -> list[tuple[AccountRecord, CookieValidationReport]]:
        """Batch import multiple Cookie-Editor JSON files.

        :param file_paths: List of local paths to cookie JSON files.
        :return: List of tuples (AccountRecord, CookieValidationReport).
        """
        results: list[tuple[AccountRecord, CookieValidationReport]] = []
        current_count = len(self._accounts)

        for idx, fp in enumerate(file_paths):
            path = Path(fp)
            report, normalized = CookieValidator.parse_file(path)

            acc_id = str(uuid.uuid4())
            enc_file = f"{acc_id}.enc"
            enc_path = self._cookies_dir / enc_file

            # Infer username or use numbered fallback: "Conta TikTok 01", "Conta TikTok 02"
            inferred_user = ""
            m = re.match(r"^@?([\w\.\-]+?)(?:-cookie|\.cookie)?\.json$", path.name, re.IGNORECASE)
            if m:
                candidate = m.group(1).lstrip("@")
                if candidate.lower() not in ("cookie", "cookies", "export", "tiktok", "user"):
                    inferred_user = candidate

            display_idx = current_count + idx + 1
            default_title = f"Conta TikTok {display_idx:02d}"

            if report.is_valid:
                # Encrypt and save in rest
                save_encrypted_json(
                    enc_path,
                    normalized,
                    description=f"TikTok {inferred_user or default_title}",
                )
                status = AccountAuthStatus.STRUCTURALLY_VALID.value
                last_error = None
            else:
                status = AccountAuthStatus.IMPORTED.value
                last_error = "; ".join(report.errors)

            record = AccountRecord(
                account_id=acc_id,
                username=inferred_user,
                platform="tiktok",
                cookie_file=enc_file,
                department_id=None,
                auth_status=status,
                enabled=True,
                cookie_count=len(normalized) if report.is_valid else report.total_cookies,
                display_title=default_title,
                last_error=last_error,
            )

            self._accounts[acc_id] = record
            results.append((record, report))

        self._save_registry()
        return results

    def update_account(
        self,
        account_id: str,
        username: str | None = None,
        department_id: str | None = None,
        enabled: bool | None = None,
        auth_status: str | None = None,
        last_error: str | None = None,
        last_validated_at: str | None = None,
    ) -> bool:
        """Update metadata fields for a registered account."""
        acc = self.get_account(account_id)
        if not acc:
            return False

        if username is not None:
            acc.username = username.lstrip("@").strip()
        if department_id is not None:
            acc.department_id = department_id
        if enabled is not None:
            acc.enabled = enabled
        if auth_status is not None:
            acc.auth_status = auth_status
        if last_error is not None:
            acc.last_error = last_error
        if last_validated_at is not None:
            acc.last_validated_at = last_validated_at

        self._save_registry()
        return True

    def delete_account(self, account_id: str, delete_credentials: bool = True) -> bool:
        """Remove account registration and optionally securely wipe encrypted credentials.

        Preserves all publication histories and scheduling storage.
        """
        acc = self._accounts.pop(account_id, None)
        if not acc:
            return False

        if delete_credentials and acc.cookie_file:
            enc_path = self._cookies_dir / acc.cookie_file
            if enc_path.exists():
                try:
                    enc_path.unlink()
                except OSError as exc:
                    logger.warning(f"Could not delete credential file {enc_path}: {exc}")

        self._save_registry()
        return True

    async def validate_tiktok_session(
        self,
        account_id: str,
        headless: bool = True,
    ) -> tuple[bool, str, str | None]:
        """Perform READ-ONLY TikTok Studio session validation using isolated Playwright context.

        DOES NOT upload videos.
        DOES NOT schedule videos.
        DOES NOT change account settings.

        :param account_id: UUID of account to validate.
        :param headless: Run headless (default True).
        :return: (is_authenticated: bool, status_message: str, detected_username: str | None)
        """
        acc = self.get_account(account_id)
        if not acc:
            return False, "Conta não encontrada", None

        # Update status to VALIDATING
        self.update_account(account_id, auth_status=AccountAuthStatus.VALIDATING.value)

        try:
            cookies = self.load_account_cookies(account_id)
        except Exception as exc:
            msg = f"Falha ao carregar credenciais: {exc}"
            self.update_account(
                account_id,
                auth_status=AccountAuthStatus.INVALID_SESSION.value,
                last_error=msg,
            )
            return False, msg, None

        if not cookies:
            msg = "Arquivo de credenciais vazio"
            self.update_account(
                account_id,
                auth_status=AccountAuthStatus.INVALID_SESSION.value,
                last_error=msg,
            )
            return False, msg, None

        # Lazy import playwright
        from playwright.async_api import async_playwright

        detected_user: str | None = None
        playwright_obj = None
        browser = None
        context = None

        try:
            playwright_obj = await async_playwright().start()
            browser = await playwright_obj.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )

            await context.add_cookies(cookies)
            page = await context.new_page()

            # Read-only navigation to TikTok Studio
            studio_url = "https://www.tiktok.com/tiktokstudio"
            response = await page.goto(studio_url, wait_until="domcontentloaded", timeout=45000)

            await asyncio.sleep(3)

            current_url = page.url.lower()

            # 1. Check for login redirect
            if "login" in current_url and "tiktokstudio" not in current_url:
                self.update_account(
                    account_id,
                    auth_status=AccountAuthStatus.INVALID_SESSION.value,
                    last_validated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    last_error="Sessão redirecionada para tela de login",
                )
                return False, "Sessão inválida ou expirada", None

            # 2. Check for security challenge / verification required
            has_captcha = await page.locator(".captcha_verify_container, #captcha_container, .verify-bar-close").count()
            if has_captcha > 0:
                self.update_account(
                    account_id,
                    auth_status=AccountAuthStatus.VALIDATION_REQUIRED.value,
                    last_validated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    last_error="Verificação de segurança (CAPTCHA) exigida pelo TikTok",
                )
                return False, "Verificação necessária (CAPTCHA)", None

            # 3. Detect logged-in username from DOM
            # Inspect links with /@ in href first (most reliable on TikTok Studio header)
            try:
                for a in await page.locator("a[href*='/@']").all():
                    href = await a.get_attribute("href")
                    if href:
                        m = re.search(r"/@([\w\.\-]+)", href)
                        if m:
                            detected_user = m.group(1).strip()
                            break
                    txt = await a.text_content()
                    if txt and txt.strip():
                        detected_user = txt.strip().lstrip("@")
                        break
            except Exception:
                pass

            if not detected_user:
                user_selectors = [
                    "[data-tt='header-user-info']",
                    ".user-info-name",
                    "span[class*='user-info']",
                    "p[class*='unique-id']",
                ]

                for sel in user_selectors:
                    try:
                        loc = page.locator(sel)
                        if await loc.count() > 0:
                            for i in range(await loc.count()):
                                text = await loc.nth(i).text_content()
                                if text and text.strip():
                                    detected_user = text.strip().lstrip("@")
                                    break
                            if detected_user:
                                break
                    except Exception:
                        continue

            # Check page HTML for user handle if selector didn't catch it
            if not detected_user:
                try:
                    content = await page.content()
                    m = re.search(r'"uniqueId"\s*:\s*"([^"]+)"', content)
                    if m:
                        detected_user = m.group(1)
                except Exception:
                    pass

            is_studio = "tiktokstudio" in page.url.lower() and "login" not in page.url.lower()
            has_upload = await page.locator("input[type='file'], a[href*='upload'], button:has-text('Upload'), span:has-text('Upload')").count()

            if (is_studio and detected_user) or has_upload > 0:
                final_user = detected_user or acc.username
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.update_account(
                    account_id,
                    username=final_user,
                    auth_status=AccountAuthStatus.AUTHENTICATED.value,
                    last_validated_at=now_str,
                    last_error=None,
                )
                return True, "Sessão autenticada com sucesso", final_user

            # If studio could not be confirmed
            self.update_account(
                account_id,
                auth_status=AccountAuthStatus.VALIDATION_REQUIRED.value,
                last_validated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_error="Ambiente do estúdio não confirmado",
            )
            return False, "Validação pendente ou incompleta", None

        except Exception as exc:
            err_msg = f"Erro na validação: {exc}"
            logger.error(err_msg)
            self.update_account(
                account_id,
                auth_status=AccountAuthStatus.INVALID_SESSION.value,
                last_error=err_msg,
            )
            return False, err_msg, None

        finally:
            # Strictly teardown and close context and browser
            try:
                if context is not None:
                    await context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass
            try:
                if playwright_obj is not None:
                    await playwright_obj.stop()
            except Exception:
                pass
