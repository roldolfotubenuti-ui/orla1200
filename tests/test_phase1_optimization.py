import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import async_playwright

from core.dom_handler import DOMHandler
from core.logger_manager import LoggerManager
from core.uploader import Uploader, UploadTask, UploadResult
from utils.datetime_utils import DateTimeUtils


class TestPhase1Optimization(unittest.IsolatedAsyncioTestCase):
  """Comprehensive test suite for Phase 1 optimizations: caption filling,

  content quality check non-blocking logic, post button state, and telemetry.
  """

  @classmethod
  def setUpClass(cls) -> None:
    cls.logger = LoggerManager()
    cls.dt_utils = DateTimeUtils()

  async def test_caption_short_and_long(self) -> None:
    """Validate filling short and long captions on contenteditable element."""
    async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()
      await page.set_content("""
        <html><body>
          <div contenteditable='true' style='min-height: 50px;'></div>
        </body></html>
      """)
      dom = DOMHandler(page, self.logger, self.dt_utils)

      # 1. Short caption
      short_text = "Vídeo curto #shorts"
      await dom.set_caption(short_text)
      editor = page.locator("div[contenteditable='true']").first
      self.assertEqual((await editor.inner_text()).strip(), short_text.strip())

      # 2. Long caption (1000+ characters)
      long_text = "Esta é uma legenda longa de teste com múltiplos parágrafos.\n" * 20 + "#viral #fyp"
      await dom.set_caption(long_text)
      current = (await editor.inner_text()).strip()
      self.assertIn("#viral #fyp", current)
      self.assertGreater(len(current), 500)

      await browser.close()

  async def test_caption_accents_emojis_linebreaks_hashtags(self) -> None:
    """Validate preservation of unicode accents, emojis, linebreaks, and hashtags."""
    async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()
      await page.set_content("""
        <html><body>
          <div contenteditable='true'></div>
        </body></html>
      """)
      dom = DOMHandler(page, self.logger, self.dt_utils)

      text = (
        "🚀 Vídeo Épico de Futebol! 🔥⚽\n"
        "Golaço com coração, emoção e bênção!\n"
        "Linha 3 com acentuação: ação, café, avô.\n"
        "#futebol #gol #brasil2026 🎉"
      )
      await dom.set_caption(text)
      editor = page.locator("div[contenteditable='true']").first
      captured = (await editor.inner_text()).strip()

      self.assertIn("🚀", captured)
      self.assertIn("🔥⚽", captured)
      self.assertIn("coração, emoção e bênção!", captured)
      self.assertIn("ação, café, avô", captured)
      self.assertIn("#futebol #gol #brasil2026 🎉", captured)
      self.assertEqual(captured.count("\n"), 3)

      await browser.close()

  async def test_post_button_disabled_vs_enabled(self) -> None:
    """Validate detection of enabled vs disabled post button states."""
    async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()

      dom = DOMHandler(page, self.logger, self.dt_utils)

      # 1. Enabled button
      await page.set_content("""
        <button data-e2e="post_video_button">Post</button>
      """)
      self.assertTrue(await dom.is_post_button_enabled())

      # 2. Disabled attribute
      await page.set_content("""
        <button data-e2e="post_video_button" disabled>Post</button>
      """)
      self.assertFalse(await dom.is_post_button_enabled())

      # 3. aria-disabled="true"
      await page.set_content("""
        <button data-e2e="post_video_button" aria-disabled="true">Post</button>
      """)
      self.assertFalse(await dom.is_post_button_enabled())

      # 4. class="btn-disabled"
      await page.set_content("""
        <button data-e2e="post_video_button" class="btn disabled-button">Post</button>
      """)
      self.assertFalse(await dom.is_post_button_enabled())

      # 5. Not visible (display: none)
      await page.set_content("""
        <button data-e2e="post_video_button" style="display: none;">Post</button>
      """)
      self.assertFalse(await dom.is_post_button_enabled())

      await browser.close()

  async def test_content_quality_pending_with_button_enabled(self) -> None:
    """Validate that when content check is pending (status-ready or status-checking),

    if post button is already enabled, it does NOT block and returns immediately.
    """
    async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()
      # Page has status-checking, but post button is enabled
      await page.set_content("""
        <div>
          <div class="status-result status-checking" data-show="true">Checking...</div>
          <button data-e2e="post_video_button">Schedule</button>
        </div>
      """)
      dom = DOMHandler(page, self.logger, self.dt_utils)

      import time
      t0 = time.monotonic()
      res = await dom.check_content_quality(max_wait_seconds=10)
      elapsed = time.monotonic() - t0

      self.assertLess(elapsed, 2.0, "Must return immediately when button is enabled")
      self.assertEqual(res.get("state"), "checking")
      self.assertFalse(res.get("blocking", True))
      self.assertTrue(res.get("pending", False))

      # Test status-ready (initial preparatory state)
      await page.set_content("""
        <div>
          <div class="status-result status-ready" data-show="true">We will check...</div>
          <button data-e2e="post_video_button">Schedule</button>
        </div>
      """)
      t0 = time.monotonic()
      res_ready = await dom.check_content_quality(max_wait_seconds=10)
      elapsed_ready = time.monotonic() - t0

      self.assertLess(elapsed_ready, 2.0)
      self.assertEqual(res_ready.get("state"), "ready")
      self.assertFalse(res_ready.get("blocking", True))
      self.assertTrue(res_ready.get("pending", False))

      await browser.close()

  async def test_content_quality_concluded_states(self) -> None:
    """Validate concluded non-blocking states (status-success, status-warn, status-limit, status-not-eligible)."""
    async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()
      dom = DOMHandler(page, self.logger, self.dt_utils)

      test_cases = [
        ("status-success", "success", False),
        ("status-warn", "warning", False),
        ("status-not-eligible", "notEligible", False),
      ]

      for status_cls, expected_state, expected_blocking in test_cases:
        await page.set_content(f"""
          <div>
            <div class="status-result {status_cls}" data-show="true">Result text</div>
            <button data-e2e="post_video_button">Post</button>
          </div>
        """)
        res = await dom.check_content_quality(max_wait_seconds=5)
        self.assertEqual(res.get("state"), expected_state)
        self.assertEqual(res.get("blocking"), expected_blocking)

      await browser.close()

  async def test_content_quality_blocking_error(self) -> None:
    """Validate that status-error with disabled post button blocks submission."""
    async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()
      await page.set_content("""
        <div>
          <div class="status-result status-error" data-show="true">Something went wrong</div>
          <button data-e2e="post_video_button" disabled>Post</button>
        </div>
      """)
      dom = DOMHandler(page, self.logger, self.dt_utils)

      res = await dom.check_content_quality(max_wait_seconds=3)
      self.assertEqual(res.get("state"), "error")
      self.assertTrue(res.get("blocking"))

      await browser.close()

  async def test_communication_failure(self) -> None:
    """Validate graceful handling when DOM evaluation raises an error."""
    mock_page = MagicMock()
    mock_page.evaluate = AsyncMock(side_effect=Exception("Page crashed / disconnected"))
    mock_page.locator = MagicMock()
    btn_mock = MagicMock()
    btn_mock.count = AsyncMock(return_value=0)
    mock_page.locator.return_value.first = btn_mock

    dom = DOMHandler(mock_page, self.logger, self.dt_utils)
    res = await dom.check_content_quality(max_wait_seconds=2)
    # Must not raise unhandled crash, and report failure to proceed safely
    self.assertTrue(res.get("blocking"))

  async def test_telemetry_integration_in_uploader(self) -> None:
    """Validate that Uploader measures every step with monotonic clock and outputs structured telemetry."""
    class MockDOM:
      def __init__(self):
        self.clicked = False
      async def dismiss_all_popups(self): pass
      async def upload_file(self, fp): await asyncio.sleep(0.02)
      async def wait_upload_complete(self, timeout=120): return True
      async def set_caption(self, text): await asyncio.sleep(0.01)
      async def enable_schedule(self): pass
      async def dismiss_allow_schedule(self): pass
      async def set_time(self, h, m): await asyncio.sleep(0.01)
      async def set_date(self, d, m, y): await asyncio.sleep(0.01)
      async def set_visibility(self, mode): pass
      async def check_music_copyright(self): return {"has_copyright": False, "message": "OK"}
      async def check_content_quality(self): return {"state": "checking", "message": "In progress", "blocking": False}
      async def is_post_button_enabled(self): return True
      async def click_post(self): self.clicked = True; await asyncio.sleep(0.01)
      async def handle_all_post_modals(self): pass
      async def wait_post_complete(self, timeout=60): await asyncio.sleep(0.02); return True

    mock_dom = MockDOM()
    uploader = Uploader(mock_dom, self.logger)
    from datetime import datetime, timedelta
    sch_time = datetime.now() + timedelta(days=2)
    task = UploadTask(file_path=Path("test_video.mp4"), caption="Legenda 🚀 #teste", schedule_time=sch_time)

    telemetry_base = {
      "browser_init_sec": 1.25,
      "studio_load_sec": 3.40,
      "auth_sec": 0.30,
    }

    result = await uploader.upload_video(task, telemetry_base=telemetry_base, username="test_user")

    self.assertTrue(result.success)
    self.assertTrue(mock_dom.clicked)
    self.assertIsNotNone(result.telemetry)

    t = result.telemetry
    self.assertEqual(t["browser_init_sec"], 1.25)
    self.assertEqual(t["studio_load_sec"], 3.40)
    self.assertEqual(t["auth_sec"], 0.30)
    self.assertGreater(t["upload_sec"], 0.01)
    self.assertGreater(t["caption_sec"], 0.005)
    self.assertGreater(t["time_config_sec"], 0.005)
    self.assertGreater(t["date_config_sec"], 0.005)
    self.assertGreater(t["submission_sec"], 0.005)
    self.assertGreater(t["confirmation_sec"], 0.01)
    self.assertGreater(t["total_sec"], 4.9)


if __name__ == "__main__":
  unittest.main()
