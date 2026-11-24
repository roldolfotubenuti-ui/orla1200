from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from playwright.async_api import (
  Browser,
  BrowserContext,
  Page,
  Playwright,
  async_playwright,
)

from core.cookie_manager import CookieManager
from core.logger_manager import LoggerManager


class AuthenticationError(Exception):
  """
  Raised when TikTok session authentication fails.
  """


class BrowserManager:
  """
  Manages the full Playwright browser lifecycle for TikTok Studio.

  Handles launching Chromium, creating browser contexts, injecting cookies,
  navigating to the upload page, verifying login status, and teardown.

  :param cookie_manager: CookieManager instance for loading cookies.
  :type cookie_manager: CookieManager
  :param logger: Logger instance for status messages.
  :type logger: LoggerManager
  :param headless: Whether to run the browser without a visible window.
  :type headless: bool
  """

  UPLOAD_URL: str = "https://www.tiktok.com/tiktokstudio/upload?from=webapp"
  LOGIN_URL_FRAGMENT: str = "login"
  FILE_INPUT_SELECTOR: str = "input[type='file']"

  DEFAULT_VIEWPORT: dict[str, int] = {"width": 1920, "height": 1080}
  DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
  )

  DEFAULT_TIMEOUT: int = 30000     # 30 seconds (locator actions)
  NAVIGATION_TIMEOUT: int = 60000  # 60 seconds
  LOGIN_CHECK_TIMEOUT: int = 10000  # 10 seconds

  def __init__(
    self,
    cookie_manager: CookieManager,
    logger: LoggerManager,
    headless: bool = True,
  ) -> None:
    """
    Initialize BrowserManager.

    :param cookie_manager: CookieManager instance for loading cookies.
    :type cookie_manager: CookieManager
    :param logger: Logger instance.
    :type logger: LoggerManager
    :param headless: Run browser without visible window.
    :type headless: bool
    """
    self._cookie_manager = cookie_manager
    self._logger = logger
    self._headless = headless

    self._playwright: Playwright | None = None
    self._browser: Browser | None = None
    self._context: BrowserContext | None = None
    self._page: Page | None = None
    self._current_username: str | None = None
    self.restart_count: int = 0
    self.session_video_count: int = 0
    self.telemetry: dict = {
      "browser_init_sec": 0.0,
      "studio_load_sec": 0.0,
      "auth_sec": 0.0,
      "browser_reused": False,
      "session_reused": False,
      "page_reloaded": False,
      "browser_recovery_sec": 0.0,
      "browser_restart_count": 0,
      "videos_processed_per_browser_session": 0,
    }

  async def is_session_healthy(self) -> bool:
    """
    Check if the browser, context, and page are alive and responsive.

    :return: True if the session is alive and responding.
    :rtype: bool
    """
    if self._browser is None:
      return False
    try:
      conn = self._browser.is_connected()
      if asyncio.iscoroutine(conn):
        conn = await conn
      if not conn:
        return False
    except Exception:
      return False

    if self._context is None:
      return False
    if self._page is None:
      return False

    try:
      closed = self._page.is_closed()
      if asyncio.iscoroutine(closed):
        closed = await closed
      if closed:
        return False
    except Exception:
      return False

    try:
      current_url = await self._page.evaluate("() => document.location.href")
      if not current_url or self.LOGIN_URL_FRAGMENT in str(current_url).lower():
        return False
      return True
    except Exception:
      return False

  async def close_context(self) -> None:
    """
    Close the current account context and active page without stopping
    the underlying Chromium process or Playwright instance.

    Used when switching accounts to guarantee strict cookie and session isolation.
    """
    if self._page is not None:
      try:
        closed = self._page.is_closed()
        if asyncio.iscoroutine(closed):
          closed = await closed
        if not closed:
          await self._page.close()
      except Exception as e:
        self._logger.debug(f"Error closing page: {e}")
      self._page = None

    if self._context is not None:
      try:
        await self._context.close()
      except Exception as e:
        self._logger.debug(f"Error closing context: {e}")
      self._context = None

    self._current_username = None
    self.session_video_count = 0

  async def launch(self, username: str) -> None:
    """
    Launch browser or reuse active session, create context, inject cookies,
    and navigate to upload page.

    Strict account isolation:
    - If already running for the SAME username, validates session health and reuses it.
    - If a DIFFERENT username is provided, cleanly closes the previous context
      before initiating the new account's isolated context.

    :param username: TikTok account username to load cookies for.
    :type username: str
    :raises AuthenticationError: If login verification fails after navigation.
    """
    # 1. Check if browser connection is alive
    is_connected = False
    if self._browser is not None:
      try:
        conn = self._browser.is_connected()
        if asyncio.iscoroutine(conn):
          conn = await conn
        is_connected = bool(conn)
      except Exception:
        is_connected = False

    # 2. Check if an active session already exists
    if self._browser is not None and is_connected and self._context is not None:
      if self._current_username == username:
        # Same account! Check health and reuse
        if await self.is_session_healthy():
          self.session_video_count += 1
          self.telemetry.update({
            "browser_init_sec": 0.0,
            "auth_sec": 0.0,
            "browser_reused": True,
            "session_reused": True,
            "page_reloaded": False,
            "browser_recovery_sec": 0.0,
            "browser_restart_count": self.restart_count,
            "videos_processed_per_browser_session": self.session_video_count,
          })
          self._logger.info(
            f"Reusing existing authenticated Chromium session for @{username} (video #{self.session_video_count})"
          )
          return
        else:
          self._logger.warning("Existing session unhealthy — initiating session recovery")
          await self.recover_session(username)
          return
      else:
        # Different account! Strict isolation: close previous context and cookies
        self._logger.info(
          f"Account switch detected (@{self._current_username} -> @{username}) — closing previous context for isolation"
        )
        await self.close_context()

    self._logger.info(f"Launching browser session for @{username}")
    self._current_username = username
    t_browser_start = time.monotonic()

    # Start Playwright if needed
    if self._playwright is None:
      self._playwright = await async_playwright().start()

    # Check cookies first before launching browser
    cookies = self._cookie_manager.load_cookie(username)
    if not cookies:
      raise AuthenticationError(
        f"Nenhum cookie encontrado para @{username}. Por favor, conecte a conta ou importe os cookies na aba Contas."
      )

    # Launch Chromium if not running or disconnected
    if self._browser is None or not is_connected:
      try:
        self._browser = await self._playwright.chromium.launch(
          headless=self._headless,
          args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
          ],
        )
      except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
          self._logger.info("Chromium não encontrado. Baixando navegador de automação automaticamente...")
          from utils.app_paths import ensure_playwright_chromium
          ensure_playwright_chromium(logger_fn=self._logger.info)
          self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=[
              "--disable-blink-features=AutomationControlled",
              "--no-sandbox",
            ],
          )
        else:
          raise

    # Create isolated context for this account
    self._context = await self._configure_context()

    # Load and inject cookies
    await self._inject_cookies(cookies)
    t_browser_sec = time.monotonic() - t_browser_start

    # Create page and navigate
    t_load_start = time.monotonic()
    self._page = await self._context.new_page()
    await self.navigate_to_upload()
    t_load_sec = time.monotonic() - t_load_start

    # Verify login
    t_auth_start = time.monotonic()
    logged_in = await self.is_logged_in()
    t_auth_sec = time.monotonic() - t_auth_start

    if not logged_in:
      await self.close_context()
      raise AuthenticationError(
        f"Authentication failed for @{username}. "
        "Cookie may be expired or invalid."
      )

    self.session_video_count = 1
    self.telemetry = {
      "browser_init_sec": t_browser_sec,
      "studio_load_sec": t_load_sec,
      "auth_sec": t_auth_sec,
      "browser_reused": False,
      "session_reused": False,
      "page_reloaded": False,
      "browser_recovery_sec": 0.0,
      "browser_restart_count": self.restart_count,
      "videos_processed_per_browser_session": self.session_video_count,
    }

    self._logger.success(f"Browser ready for @{username} (Session established)")

  def get_page(self) -> Page:
    """
    Return the current active Playwright Page.

    :return: The active page object.
    :rtype: Page
    :raises RuntimeError: If the browser has not been launched.
    """
    if self._page is None:
      raise RuntimeError("Browser not launched. Call launch() first.")
    return self._page

  async def is_logged_in(self) -> bool:
    """
    Check if the TikTok session is valid after navigation.

    Verifies that:
    1. The URL still contains 'tiktokstudio/upload' (no login redirect).
    2. The file input element is present on the page.

    :return: True if the session is authenticated.
    :rtype: bool
    """
    if self._page is None:
      return False

    return await self._verify_login()

  async def navigate_to_upload(self) -> None:
    """
    Navigate the active page to the TikTok Studio upload URL.

    :raises RuntimeError: If no page is available.
    """
    if self._page is None:
      raise RuntimeError("No active page. Call launch() first.")

    self._logger.info(f"Navigating to {self.UPLOAD_URL}")
    await self._page.goto(
      self.UPLOAD_URL,
      wait_until="domcontentloaded",
      timeout=self.NAVIGATION_TIMEOUT,
    )

    # Allow page JS to settle — do NOT use networkidle because TikTok
    # keeps persistent WebSocket connections open indefinitely, which
    # causes networkidle to hang until timeout.
    await asyncio.sleep(3)
    self._logger.debug("Page loaded successfully")

  async def close(self) -> None:
    """
    Close the browser, context, and Playwright instance gracefully.

    Safe to call multiple times.
    """
    self._logger.info("Closing browser")

    await self.close_context()

    try:
      if self._browser is not None:
        await self._browser.close()
        self._browser = None
    except Exception as e:
      self._logger.debug(f"Error closing browser: {e}")

    try:
      if self._playwright is not None:
        await self._playwright.stop()
        self._playwright = None
    except Exception as e:
      self._logger.debug(f"Error stopping playwright: {e}")

    self._current_username = None
    self.session_video_count = 0
    self._logger.debug("Browser closed")

  async def restart(self, username: str) -> None:
    """
    Close the current browser session and re-launch with a fresh context.

    :param username: TikTok account username to use for the new session.
    :type username: str
    """
    self._logger.info(f"Restarting browser for @{username}")
    await self.close()
    await self.launch(username)

  async def prepare_for_next_video(self) -> Page:
    """
    Reset and prepare the upload form for the next video without closing the browser.

    Reuses the active page, navigates to the upload URL, waits for the file input
    element to be attached, and verifies login session.

    :return: Active Page ready for the next video.
    :rtype: Page
    """
    t_load_start = time.monotonic()
    self.session_video_count += 1

    if not await self.is_session_healthy():
      self._logger.warning("Session unhealthy before next video — recovering session")
      return await self.recover_session(self._current_username or "")

    page_reloaded = False
    try:
      current_url = self._page.url.lower() if self._page else ""
      if "upload" in current_url:
        file_input = self._page.locator(self.FILE_INPUT_SELECTOR)
        if await file_input.count() > 0 and await file_input.first.is_attached():
          await self._page.goto(
            self.UPLOAD_URL,
            wait_until="domcontentloaded",
            timeout=self.NAVIGATION_TIMEOUT,
          )
          page_reloaded = True
        else:
          await self.navigate_to_upload()
          page_reloaded = True
      else:
        await self.navigate_to_upload()
        page_reloaded = True

      # Wait for file input element to be attached and ready
      file_input = self._page.locator(self.FILE_INPUT_SELECTOR)
      await file_input.wait_for(state="attached", timeout=self.DEFAULT_TIMEOUT)

      # Validate session still logged in
      if not await self.is_logged_in():
        self._logger.warning("Login lost after navigation — attempting recovery")
        return await self.recover_session(self._current_username or "")

      t_load_sec = time.monotonic() - t_load_start
      self.telemetry.update({
        "browser_init_sec": 0.0,
        "studio_load_sec": t_load_sec,
        "auth_sec": 0.0,
        "browser_reused": True,
        "session_reused": True,
        "page_reloaded": page_reloaded,
        "browser_recovery_sec": 0.0,
        "browser_restart_count": self.restart_count,
        "videos_processed_per_browser_session": self.session_video_count,
      })
      self._logger.info(
        f"Page ready for next video (Session reused, {t_load_sec:.2f}s)"
      )
      return self._page

    except Exception as exc:
      self._logger.warning(f"Error preparing page for next video: {exc} — recovering session")
      return await self.recover_session(self._current_username or "")

  async def recover_session(self, username: str) -> Page:
    """
    Recover a crashed, disconnected, or unresponsive browser session.

    Increments the restart count, measures recovery time, and re-establishes
    an isolated authenticated context for the given user.

    :param username: TikTok account username.
    :type username: str
    :return: Newly recovered active Page.
    :rtype: Page
    """
    t_rec_start = time.monotonic()
    self.restart_count += 1
    self._logger.info(
      f"Recovering browser session for @{username} (recovery event #{self.restart_count})..."
    )

    await self.close_context()

    browser_conn = False
    if self._browser is not None:
      try:
        conn = self._browser.is_connected()
        if asyncio.iscoroutine(conn):
          conn = await conn
        browser_conn = bool(conn)
      except Exception:
        browser_conn = False

    if not browser_conn:
      try:
        if self._browser is not None:
          await self._browser.close()
      except Exception:
        pass
      self._browser = None

    await self.launch(username)
    t_rec_sec = time.monotonic() - t_rec_start
    self.telemetry["browser_recovery_sec"] = t_rec_sec
    self.telemetry["browser_restart_count"] = self.restart_count
    self._logger.success(f"Session recovered successfully in {t_rec_sec:.2f}s")
    return self.get_page()

  async def new_upload_page(self) -> None:
    """
    Navigate to a fresh upload page for the next video.
    Maintained for backward compatibility.
    """
    await self.prepare_for_next_video()

  async def _inject_cookies(self, cookies: list[dict[str, Any]]) -> None:
    """
    Add cookies to the browser context.

    :param cookies: List of Playwright-compatible cookie dictionaries.
    :type cookies: list[dict[str, Any]]
    """
    if self._context is None:
      raise RuntimeError("No active context")

    await self._context.add_cookies(cookies)
    self._logger.debug(f"Injected {len(cookies)} cookie(s)")

  async def _verify_login(self) -> bool:
    """
    Verify that the current page state indicates a valid login session.

    Checks URL for login redirects and probes for the file upload input.

    :return: True if login is verified.
    :rtype: bool
    """
    if self._page is None:
      return False

    current_url = self._page.url.lower()

    # Check for login redirect
    if self.LOGIN_URL_FRAGMENT in current_url and "upload" not in current_url:
      self._logger.error("Redirected to login page -- session invalid")
      return False

    # Check for file input element
    try:
      file_input = self._page.locator(self.FILE_INPUT_SELECTOR)
      await file_input.wait_for(
        state="attached",
        timeout=self.LOGIN_CHECK_TIMEOUT,
      )
      self._logger.debug("Login verified -- file input found")
      return True
    except Exception:
      self._logger.error("File input not found -- login may have failed")
      return False

  async def _configure_context(self) -> BrowserContext:
    """
    Create a browser context with realistic viewport, user-agent, and locale.

    :return: Configured BrowserContext.
    :rtype: BrowserContext
    """
    if self._browser is None:
      raise RuntimeError("Browser not launched")

    context = await self._browser.new_context(
      viewport=self.DEFAULT_VIEWPORT,
      user_agent=self.DEFAULT_USER_AGENT,
      locale="en-US",
    )

    # Set default timeouts on the context so every locator and
    # navigation call inherits them (matches old working code).
    t1 = context.set_default_timeout(self.DEFAULT_TIMEOUT)
    if asyncio.iscoroutine(t1):
      t1.close()
    t2 = context.set_default_navigation_timeout(self.NAVIGATION_TIMEOUT)
    if asyncio.iscoroutine(t2):
      t2.close()

    return context
