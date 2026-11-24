"""BrowserRuntime service for centralized Chromium process and context lifecycle.

Maintains a single running Chromium browser process for TKS Engine, delegating
isolated account BrowserContexts to ContextRegistry and handling graceful recovery.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from core.account_manager import AccountManager
from core.context_registry import ContextRegistry

logger = logging.getLogger("tks.browser_runtime")


class BrowserRuntime:
    """Central manager for Playwright Chromium lifecycle and multiaccount isolation."""

    def __init__(self, context_registry: ContextRegistry | None = None) -> None:
        self._registry = context_registry or ContextRegistry()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._headless: bool = True
        self._lock = asyncio.Lock()
        self._is_starting: bool = False

    @property
    def context_registry(self) -> ContextRegistry:
        return self._registry

    @property
    def browser(self) -> Browser | None:
        return self._browser

    @property
    def is_running(self) -> bool:
        return self.is_alive()

    def is_alive(self) -> bool:
        """Check if browser process is alive and connected."""
        if self._browser is None or self._playwright is None:
            return False
        try:
            return self._browser.is_connected()
        except Exception:
            return False

    async def start(self, headless: bool = True) -> Browser:
        """Start Playwright and launch Chromium browser process if not already running."""
        async with self._lock:
            if self.is_alive():
                return self._browser  # type: ignore[return-value]

            self._headless = headless
            logger.info(f"Starting BrowserRuntime (Chromium headless={headless})...")

            if self._playwright is None:
                self._playwright = await async_playwright().start()

            # Launch Chromium with anti-detection and stability arguments
            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ]

            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=args,
            )

            # Listen for browser disconnect to trigger recovery awareness
            self._browser.on("disconnected", self._on_browser_disconnected)

            logger.info("BrowserRuntime started successfully.")
            return self._browser

    def _on_browser_disconnected(self) -> None:
        """Handler called if Chromium process terminates unexpectedly."""
        logger.warning("Chromium process disconnected unexpectedly.")
        self._browser = None

    async def ensure_browser(self, headless: bool | None = None) -> Browser:
        """Ensure the browser process is running, restarting it if it disconnected."""
        if headless is None:
            headless = self._headless

        if not self.is_alive():
            logger.info("Browser process not alive; restarting BrowserRuntime...")
            # Close existing contexts before launching anew
            await self._registry.close_all()
            return await self.start(headless=headless)

        return self._browser  # type: ignore[return-value]

    async def get_or_create_account_session(
        self,
        account_id: str,
        account_manager: AccountManager,
    ) -> tuple[BrowserContext, Page]:
        """Obtain an isolated BrowserContext and Page for an account, starting browser if needed."""
        browser = await self.ensure_browser()
        return await self._registry.get_or_create_context(
            browser=browser,
            account_id=account_id,
            account_manager=account_manager,
        )

    async def close_account_session(self, account_id: str) -> bool:
        """Close an account's isolated session."""
        return await self._registry.close_context(account_id)

    async def stop(self) -> None:
        """Gracefully close all account contexts, disconnect Chromium, and stop Playwright."""
        async with self._lock:
            logger.info("Stopping BrowserRuntime and cleaning up resources...")
            try:
                await self._registry.close_all()
            except Exception as exc:
                logger.warning(f"Error during context registry teardown: {exc}")

            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception as exc:
                    logger.debug(f"Error closing browser: {exc}")
                self._browser = None

            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception as exc:
                    logger.debug(f"Error stopping playwright: {exc}")
                self._playwright = None

            logger.info("BrowserRuntime stopped.")
