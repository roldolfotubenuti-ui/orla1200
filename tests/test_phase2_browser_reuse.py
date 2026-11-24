import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from core.browser_manager import BrowserManager, AuthenticationError
from core.cookie_manager import CookieManager
from core.dom_handler import DOMHandler
from core.logger_manager import LoggerManager
from core.scheduler import UploadTask
from core.uploader import Uploader, UploadResult
from gui.controllers.upload_worker import UploadWorker
from utils.datetime_utils import DateTimeUtils


class TestPhase2BrowserReuse(unittest.IsolatedAsyncioTestCase):
  """Comprehensive test suite for Phase 2: Chromium reuse, account isolation,

  page preparation, recovery, and duplicate submission prevention.
  """

  @classmethod
  def setUpClass(cls) -> None:
    cls.logger = LoggerManager()
    cls.dt_utils = DateTimeUtils()

  @staticmethod
  def _setup_mock_page(mock_page: AsyncMock) -> None:
    mock_page.is_closed = MagicMock(return_value=False)
    mock_page.url = "https://www.tiktok.com/creator-center/upload?from=webapp"
    mock_page.evaluate = AsyncMock(return_value="https://www.tiktok.com/creator-center/upload?from=webapp")
    mock_page.goto = AsyncMock()
    loc = MagicMock()
    loc.count = AsyncMock(return_value=1)
    loc.first = MagicMock()
    loc.first.is_attached = AsyncMock(return_value=True)
    loc.wait_for = AsyncMock()
    mock_page.locator = MagicMock(return_value=loc)

  async def test_1_single_video_queue(self) -> None:
    """1. Queue with a single video launches browser once."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.return_value = [{"name": "sid", "value": "xyz", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_browser.is_connected.return_value = True
      mock_context = AsyncMock()
      mock_page = AsyncMock()
      self._setup_mock_page(mock_page)

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
      mock_browser.new_context = AsyncMock(return_value=mock_context)
      mock_context.new_page = AsyncMock(return_value=mock_page)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=True)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          await bm.launch("user_one")

          self.assertEqual(bm.session_video_count, 1)
          self.assertFalse(bm.telemetry["browser_reused"])
          self.assertFalse(bm.telemetry["session_reused"])
          self.assertEqual(bm.telemetry["videos_processed_per_browser_session"], 1)

          await bm.close()
          mock_browser.close.assert_awaited()

  async def test_2_five_videos_same_account_single_browser_launch(self) -> None:
    """2. Queue with 5 videos for the same account uses a SINGLE Chromium launch and 4 session reuses."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.return_value = [{"name": "sid", "value": "xyz", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_browser.is_connected.return_value = True
      mock_context = AsyncMock()
      mock_page = AsyncMock()
      self._setup_mock_page(mock_page)

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
      mock_browser.new_context = AsyncMock(return_value=mock_context)
      mock_context.new_page = AsyncMock(return_value=mock_page)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=True)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          # Launch video 1
          await bm.launch("account_alpha")
          self.assertFalse(bm.telemetry["browser_reused"])
          self.assertEqual(bm.session_video_count, 1)

          # Videos 2 through 5 prepare page on the same browser
          for i in range(2, 6):
            page = await bm.prepare_for_next_video()
            self.assertTrue(bm.telemetry["browser_reused"])
            self.assertTrue(bm.telemetry["session_reused"])
            self.assertEqual(bm.telemetry["browser_init_sec"], 0.0)
            self.assertEqual(bm.telemetry["videos_processed_per_browser_session"], i)

          # Verify Chromium launch was called EXACTLY ONCE
          self.assertEqual(mock_pw.chromium.launch.await_count, 1)

          await bm.close()

  async def test_3_ten_videos_same_account(self) -> None:
    """3. Queue with 10 videos processes all 10 on a single browser instance."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.return_value = [{"name": "sid", "value": "xyz", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_browser.is_connected.return_value = True
      mock_context = AsyncMock()
      mock_page = AsyncMock()
      self._setup_mock_page(mock_page)

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
      mock_browser.new_context = AsyncMock(return_value=mock_context)
      mock_context.new_page = AsyncMock(return_value=mock_page)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=True)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          await bm.launch("account_scale")
          for _ in range(9):
            await bm.prepare_for_next_video()

          self.assertEqual(bm.session_video_count, 10)
          self.assertEqual(mock_pw.chromium.launch.await_count, 1)
          await bm.close()

  async def test_4_account_switching_isolation(self) -> None:
    """4. Switching between different accounts completely isolates contexts and cookies."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.side_effect = lambda u: [{"name": f"cookie_{u}", "value": "val", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_browser.is_connected.return_value = True

      context_a = AsyncMock()
      context_b = AsyncMock()
      mock_browser.new_context.side_effect = [context_a, context_b]

      page_a = AsyncMock()
      self._setup_mock_page(page_a)
      page_b = AsyncMock()
      self._setup_mock_page(page_b)
      context_a.new_page.return_value = page_a
      context_b.new_page.return_value = page_b

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=True)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          # Launch Account A
          await bm.launch("conta_alfa")
          self.assertEqual(bm._current_username, "conta_alfa")
          context_a.add_cookies.assert_awaited()

          # Switch to Account B
          await bm.launch("conta_beta")
          # Context A must have been closed
          context_a.close.assert_awaited()
          # Account B context must be active
          self.assertEqual(bm._current_username, "conta_beta")
          context_b.add_cookies.assert_awaited()

          # The cookies added to Context B must belong strictly to beta
          added_cookies = context_b.add_cookies.call_args[0][0]
          self.assertEqual(added_cookies[0]["name"], "cookie_conta_beta")

          await bm.close()

  async def test_5_failure_middle_of_queue_continues(self) -> None:
    """5. Failure of a video in the middle of a queue does not crash queue and next video proceeds cleanly."""
    class MockDOM:
      def __init__(self):
        self.call_idx = 0
      async def dismiss_all_popups(self): pass
      async def upload_file(self, fp):
        self.call_idx += 1
        if self.call_idx == 2:
          raise Exception("Temporary upload glitch on video 2")
      async def wait_upload_complete(self, timeout=120): return True
      async def set_caption(self, c): pass
      async def enable_schedule(self): pass
      async def dismiss_allow_schedule(self): pass
      async def set_time(self, h, m): pass
      async def set_date(self, d, m, y): pass
      async def set_visibility(self, v): pass
      async def check_music_copyright(self): return {"has_copyright": False, "message": "OK"}
      async def check_content_quality(self): return {"state": "success", "message": "OK", "blocking": False}
      async def is_post_button_enabled(self): return True
      async def click_post(self): pass
      async def handle_all_post_modals(self): pass
      async def wait_post_complete(self, timeout=60): return True

    dom = MockDOM()
    uploader = Uploader(dom, self.logger)

    tasks = [
      UploadTask(file_path=Path("vid1.mp4"), caption="cap1"),
      UploadTask(file_path=Path("vid2_fails.mp4"), caption="cap2"),
      UploadTask(file_path=Path("vid3.mp4"), caption="cap3"),
    ]

    results = []
    for t in tasks:
      res = await uploader.upload_video(t)
      results.append(res)

    self.assertTrue(results[0].success)
    self.assertFalse(results[1].success)
    self.assertIn("Temporary upload glitch", results[1].error)
    self.assertTrue(results[2].success, "Video 3 must succeed even though Video 2 failed")

  async def test_6_session_expiration_detection(self) -> None:
    """6. Session expiration during launch raises AuthenticationError."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.return_value = [{"name": "sid", "value": "expired", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_context = AsyncMock()
      mock_page = AsyncMock()

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
      mock_browser.new_context = AsyncMock(return_value=mock_context)
      mock_context.new_page = AsyncMock(return_value=mock_page)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=False)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          with self.assertRaises(AuthenticationError):
            await bm.launch("expired_user")

  async def test_7_browser_recovery_after_disconnect(self) -> None:
    """7. Browser recovery restores session and increments restart count when disconnected."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.return_value = [{"name": "sid", "value": "val", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_browser.is_connected.return_value = True
      mock_context = AsyncMock()
      mock_page = AsyncMock()
      self._setup_mock_page(mock_page)

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
      mock_browser.new_context = AsyncMock(return_value=mock_context)
      mock_context.new_page = AsyncMock(return_value=mock_page)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=True)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          await bm.launch("recovery_user")
          self.assertEqual(bm.restart_count, 0)

          # Simulate browser disconnect
          mock_browser.is_connected.return_value = False

          # prepare_for_next_video will detect unhealthy session and recover
          await bm.prepare_for_next_video()
          self.assertEqual(bm.restart_count, 1)
          self.assertGreater(bm.telemetry["browser_recovery_sec"], 0.0)

          await bm.close()

  async def test_8_navigation_failure_handling(self) -> None:
    """8. Navigation error triggers recovery without unhandled crash."""
    mock_cookie_mgr = MagicMock(spec=CookieManager)
    mock_cookie_mgr.load_cookie.return_value = [{"name": "sid", "value": "val", "domain": ".tiktok.com", "path": "/"}]

    bm = BrowserManager(cookie_manager=mock_cookie_mgr, logger=self.logger, headless=True)

    with patch("core.browser_manager.async_playwright") as mock_pw_init:
      mock_pw = AsyncMock()
      mock_browser = AsyncMock()
      mock_browser.is_connected.return_value = True
      mock_context = AsyncMock()
      mock_page = AsyncMock()
      self._setup_mock_page(mock_page)
      mock_page.goto = AsyncMock(side_effect=Exception("Navigation network error"))

      mock_pw_init.return_value.start = AsyncMock(return_value=mock_pw)
      mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
      mock_browser.new_context = AsyncMock(return_value=mock_context)
      mock_context.new_page = AsyncMock(return_value=mock_page)

      with patch.object(bm, "is_logged_in", new=AsyncMock(return_value=True)):
        with patch.object(bm, "navigate_to_upload", new=AsyncMock()):
          await bm.launch("nav_user")
          # prepare_for_next_video handles goto exception and recovers
          await bm.prepare_for_next_video()
          self.assertGreaterEqual(bm.restart_count, 1)
          await bm.close()

  async def test_9_schedule_confirmation_flow(self) -> None:
    """9. Schedule confirmation flow returns confirmed_success and includes Phase 2 telemetry."""
    class MockDOM:
      async def dismiss_all_popups(self): pass
      async def upload_file(self, fp): pass
      async def wait_upload_complete(self, timeout=120): return True
      async def set_caption(self, c): pass
      async def enable_schedule(self): pass
      async def dismiss_allow_schedule(self): pass
      async def set_time(self, h, m): pass
      async def set_date(self, d, m, y): pass
      async def set_visibility(self, v): pass
      async def check_music_copyright(self): return {"has_copyright": False, "message": "OK"}
      async def check_content_quality(self): return {"state": "checking", "message": "In progress", "blocking": False}
      async def is_post_button_enabled(self): return True
      async def click_post(self): pass
      async def handle_all_post_modals(self): pass
      async def wait_post_complete(self, timeout=60): return True

    dom = MockDOM()
    uploader = Uploader(dom, self.logger)
    sch_time = datetime.now() + timedelta(days=1)
    task = UploadTask(file_path=Path("vid_scheduled.mp4"), caption="Test #schedule", schedule_time=sch_time)

    telemetry_base = {
      "browser_init_sec": 0.0,
      "studio_load_sec": 0.8,
      "auth_sec": 0.0,
      "browser_reused": True,
      "session_reused": True,
      "page_reloaded": True,
      "browser_recovery_sec": 0.0,
      "browser_restart_count": 0,
      "videos_processed_per_browser_session": 3,
    }

    res = await uploader.upload_video(task, telemetry_base=telemetry_base, username="scheduled_user")
    self.assertTrue(res.success)
    self.assertEqual(res.outcome, "confirmed_success")
    self.assertTrue(res.telemetry["browser_reused"])
    self.assertTrue(res.telemetry["session_reused"])
    self.assertEqual(res.telemetry["videos_processed_per_browser_session"], 3)

  async def test_10_no_duplicate_submission_on_unknown_outcome(self) -> None:
    """10. When post confirmation times out after click_post (outcome unknown),

    retry_upload NEVER attempts duplicate re-submission.
    """
    post_clicks = 0

    class MockUnknownDOM:
      async def dismiss_all_popups(self): pass
      async def upload_file(self, fp): pass
      async def wait_upload_complete(self, timeout=120): return True
      async def set_caption(self, c): pass
      async def enable_schedule(self): pass
      async def dismiss_allow_schedule(self): pass
      async def set_time(self, h, m): pass
      async def set_date(self, d, m, y): pass
      async def set_visibility(self, v): pass
      async def check_music_copyright(self): return {"has_copyright": False, "message": "OK"}
      async def check_content_quality(self): return {"state": "success", "message": "OK", "blocking": False}
      async def is_post_button_enabled(self): return True
      async def click_post(self):
        nonlocal post_clicks
        post_clicks += 1
      async def handle_all_post_modals(self): pass
      async def wait_post_complete(self, timeout=60):
        # Confirmation times out after click
        return False

    dom = MockUnknownDOM()
    uploader = Uploader(dom, self.logger)
    task = UploadTask(file_path=Path("vid_unknown.mp4"), caption="cap")

    res = await uploader.retry_upload(task, max_retries=3)
    self.assertFalse(res.success)
    self.assertEqual(res.outcome, "unknown")
    self.assertEqual(post_clicks, 1, "Must never re-click post button when outcome is unknown to prevent duplicate publication")


if __name__ == "__main__":
  unittest.main()
