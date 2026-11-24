"""Context registry for TKS Engine multiaccount browser contexts.

Manages isolated Playwright BrowserContext and Page instances per account_id,
ensuring strict isolation of cookies, localStorage, session states, and preventing
duplicate session collisions.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page

from core.account_manager import AccountManager
from core.cookie_validator import CookieValidator

logger = logging.getLogger("tks.context_registry")


class ContextRegistry:
    """Registry maintaining active BrowserContext and Page mappings for accounts."""

    def __init__(self) -> None:
        # account_id -> { "context": BrowserContext, "page": Page, "status": "ACTIVE", "created_at": str }
        self._contexts: dict[str, dict[str, Any]] = {}

    def is_context_active(self, account_id: str) -> bool:
        """Check if an active and open context exists for the account."""
        info = self._contexts.get(account_id)
        if not info:
            return False
        ctx: BrowserContext = info.get("context")
        page: Page = info.get("page")
        if ctx is None:
            return False
        try:
            # If context or page is closed, it's not active
            if page is not None and page.is_closed():
                return False
            return True
        except Exception:
            return False

    def list_active_accounts(self) -> list[str]:
        """Return list of account IDs with active sessions."""
        return [acc_id for acc_id in self._contexts if self.is_context_active(acc_id)]

    def get_context(self, account_id: str) -> BrowserContext | None:
        """Get existing BrowserContext for account if active."""
        if self.is_context_active(account_id):
            return self._contexts[account_id]["context"]
        return None

    def get_page(self, account_id: str) -> Page | None:
        """Get existing Page for account if active."""
        if self.is_context_active(account_id):
            return self._contexts[account_id]["page"]
        return None

    def get_context_status(self, account_id: str) -> str:
        """Get string status of account's context ('ACTIVE', 'IDLE', 'NONE')."""
        if self.is_context_active(account_id):
            return self._contexts[account_id].get("status", "ACTIVE")
        return "NONE"

    async def get_or_create_context(
        self,
        browser: Browser,
        account_id: str,
        account_manager: AccountManager,
        locale: str = "pt-BR",
        timezone_id: str = "America/Sao_Paulo",
    ) -> tuple[BrowserContext, Page]:
        """Retrieve existing active context or create an isolated one with DPAPI decrypted cookies.

        Prevents duplicate context creation for the same account.
        """
        # 1. Return existing if healthy
        if self.is_context_active(account_id):
            info = self._contexts[account_id]
            logger.info(f"Reusing active BrowserContext for account {account_id}")
            return info["context"], info["page"]

        # Clean up stale record if present
        if account_id in self._contexts:
            await self.close_context(account_id)

        # 2. Load account credentials
        acc = account_manager.get_account(account_id)
        if not acc:
            raise ValueError(f"Account {account_id} not found in AccountManager")

        raw_cookies = account_manager.load_account_cookies(account_id)
        normalized_cookies = CookieValidator.normalize_for_playwright(raw_cookies)

        logger.info(
            f"Creating isolated BrowserContext for account {acc.display_name} "
            f"({len(normalized_cookies)} cookies)"
        )

        # 3. Create isolated context
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale=locale,
            timezone_id=timezone_id,
            ignore_https_errors=True,
        )

        # 4. Inject decrypted cookies into this context exclusively
        if normalized_cookies:
            # Filter cookies to prevent invalid properties
            valid_pw_cookies = []
            for c in normalized_cookies:
                cookie_entry: dict[str, Any] = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c.get("path", "/"),
                    "secure": bool(c.get("secure", False)),
                    "httpOnly": bool(c.get("httpOnly", False)),
                }
                if "sameSite" in c and c["sameSite"] in ("Strict", "Lax", "None"):
                    cookie_entry["sameSite"] = c["sameSite"]
                if "expires" in c and isinstance(c["expires"], (int, float)):
                    cookie_entry["expires"] = int(c["expires"])
                valid_pw_cookies.append(cookie_entry)

            await context.add_cookies(valid_pw_cookies)

        # 4b. Permanently disable blocking Joyride tutorial overlays globally
        await context.add_init_script("""
            const disableOverlays = () => {
                const styleId = '__tks_anti_overlay_style__';
                if (!document.getElementById(styleId)) {
                    const style = document.createElement('style');
                    style.id = styleId;
                    style.innerHTML = `
                        #react-joyride-portal,
                        .react-joyride__overlay,
                        .react-joyride__tooltip,
                        div[data-test-id="overlay"],
                        div[class*="react-joyride"] {
                            display: none !important;
                            pointer-events: none !important;
                            visibility: hidden !important;
                            width: 0 !important;
                            height: 0 !important;
                        }
                    `;
                    (document.head || document.documentElement).appendChild(style);
                }
            };
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', disableOverlays);
            } else {
                disableOverlays();
            }
            setInterval(disableOverlays, 1000);
        """)

        # 5. Create default page
        page = await context.new_page()

        # 6. Register in tracking table
        self._contexts[account_id] = {
            "context": context,
            "page": page,
            "status": "ACTIVE",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account_id": account_id,
        }

        return context, page

    async def close_context(self, account_id: str) -> bool:
        """Gracefully close and discard context and pages for specific account."""
        info = self._contexts.pop(account_id, None)
        if not info:
            return False

        logger.info(f"Closing BrowserContext for account {account_id}")
        ctx: BrowserContext = info.get("context")
        page: Page = info.get("page")

        try:
            if page is not None and not page.is_closed():
                await page.close()
        except Exception as exc:
            logger.debug(f"Error closing page for account {account_id}: {exc}")

        try:
            if ctx is not None:
                await ctx.close()
        except Exception as exc:
            logger.debug(f"Error closing context for account {account_id}: {exc}")

        return True

    async def close_all(self) -> None:
        """Close all active contexts."""
        account_ids = list(self._contexts.keys())
        for acc_id in account_ids:
            try:
                await self.close_context(acc_id)
            except Exception as exc:
                logger.warning(f"Error closing context {acc_id}: {exc}")
        self._contexts.clear()

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        """Return diagnostic dictionary of all active contexts."""
        result = {}
        for acc_id, info in list(self._contexts.items()):
            active = self.is_context_active(acc_id)
            result[acc_id] = {
                "active": active,
                "status": info.get("status") if active else "DISCONNECTED",
                "created_at": info.get("created_at"),
            }
        return result
