from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from core.config_manager import ConfigManager
from core.dom_handler import DOMHandler, PostError, RateLimitError
from core.logger_manager import LoggerManager
from core.scheduler import ScheduleConfig, UploadTask
from core.uploader import UploadResult, Uploader
from gui.controller import GUIController
from gui.main_window import MainWindow
from gui.theme import ThemeManager
import setup as setup_module
from utils.datetime_utils import DateTimeUtils


class TestPostConfirmationAndUploader(unittest.IsolatedAsyncioTestCase):
  """Regression tests for Priority 1: wait_post_complete & Uploader outcomes."""

  async def asyncSetUp(self) -> None:
    self.logger = LoggerManager(name="TestPostConfirmation")
    self.dt_utils = DateTimeUtils()
    self._pw = await async_playwright().start()
    self.browser = await self._pw.chromium.launch(headless=True)
    self.context = await self.browser.new_context()

  async def asyncTearDown(self) -> None:
    await self.context.close()
    await self.browser.close()
    await self._pw.stop()

  async def test_modal_warning_does_not_return_false_positive_success(self) -> None:
    """Closing a warning modal and re-clicking Post must NOT return True without real confirmation."""
    page = await self.context.new_page()
    await page.set_content("""
      <html><body>
        <button data-e2e="post_video_button" onclick="window.postClicked = (window.postClicked || 0) + 1;">Post</button>
        <div class="common-modal-close-icon" onclick="this.remove();">X</div>
      </body></html>
    """)
    dom = DOMHandler(page, self.logger, self.dt_utils)
    ok = await dom.wait_post_complete(timeout=4)
    clicks = await page.evaluate("window.postClicked || 0")
    self.assertFalse(ok, "wait_post_complete must return False on timeout when no confirmation appears after modal close")
    self.assertEqual(clicks, 1, "Post button should be re-clicked at most once after closing warning modal")
    await page.close()

  async def test_modal_warning_followed_by_real_confirmation_succeeds(self) -> None:
    """Closing a warning modal, re-clicking Post, and then receiving confirmation text returns True."""
    page = await self.context.new_page()
    await page.set_content("""
      <html><body>
        <button data-e2e="post_video_button" onclick="
          const d = document.createElement('div');
          d.textContent = 'Your video has been scheduled';
          document.body.appendChild(d);
        ">Post</button>
        <div class="common-modal-close-icon" onclick="this.remove();">X</div>
      </body></html>
    """)
    dom = DOMHandler(page, self.logger, self.dt_utils)
    ok = await dom.wait_post_complete(timeout=6)
    self.assertTrue(ok)
    await page.close()

  async def test_hidden_post_button_alone_is_not_success(self) -> None:
    """A hidden or missing post button without redirect or confirmation text must NOT return True."""
    page = await self.context.new_page()
    await page.set_content("""
      <html><body>
        <button data-e2e="post_video_button" style="display:none;">Post</button>
      </body></html>
    """)
    dom = DOMHandler(page, self.logger, self.dt_utils)
    ok = await dom.wait_post_complete(timeout=4)
    self.assertFalse(ok)
    await page.close()

  async def test_schedule_confirmation_text_and_toast_succeed(self) -> None:
    """Both DOM text 'Your video has been scheduled' and Toast 'Video scheduled' must return True."""
    page = await self.context.new_page()
    await page.set_content("""
      <html><body>
        <button data-e2e="post_video_button">Schedule</button>
        <div>Your video has been scheduled</div>
      </body></html>
    """)
    dom = DOMHandler(page, self.logger, self.dt_utils)
    self.assertTrue(await dom.wait_post_complete(timeout=4))

    await page.set_content("""
      <html><body>
        <button data-e2e="post_video_button">Schedule</button>
        <div class="Toast-content">Video scheduled</div>
      </body></html>
    """)
    self.assertTrue(await dom.wait_post_complete(timeout=4))
    await page.close()

  async def test_toast_distinguishes_rate_limit_from_post_error(self) -> None:
    """Generic error toasts raise PostError, while rate limit toasts raise RateLimitError."""
    page = await self.context.new_page()
    dom = DOMHandler(page, self.logger, self.dt_utils)

    await page.set_content("""
      <html><body>
        <div class="Toast-content">Network error, please try again</div>
      </body></html>
    """)
    with self.assertRaises(PostError):
      await dom.wait_post_complete(timeout=4)

    await page.set_content("""
      <html><body>
        <div class="Toast-content">You are posting too fast. Take a rest and try again later.</div>
      </body></html>
    """)
    with self.assertRaises(RateLimitError):
      await dom.wait_post_complete(timeout=4)

    await page.close()

  async def test_timeout_after_post_click_is_unknown_and_never_retried(self) -> None:
    """When wait_post_complete times out after click_post(), outcome is 'unknown' and retry_upload stops immediately."""
    post_clicks = 0

    class MockTimeoutDOM:
      async def dismiss_all_popups(self): pass
      async def upload_file(self, fp): pass
      async def wait_upload_complete(self, timeout=120): return True
      async def set_caption(self, text): pass
      async def enable_schedule(self): pass
      async def dismiss_allow_schedule(self): pass
      async def set_time(self, h, m): pass
      async def set_date(self, d, m, y): pass
      async def set_visibility(self, mode): pass
      async def check_music_copyright(self): return {"has_copyright": False, "message": "No issues found."}
      async def check_content_quality(self): return {"state": "success", "message": "OK"}
      async def click_post(self):
        nonlocal post_clicks
        post_clicks += 1
      async def handle_copyright_modal(self): pass
      async def wait_post_complete(self, timeout=60):
        return False

    uploader = Uploader(MockTimeoutDOM(), self.logger)
    task = UploadTask(file_path=Path("vid_unknown.mp4"), caption="test")
    result = await uploader.retry_upload(task, max_retries=3)

    self.assertFalse(result.success)
    self.assertEqual(result.outcome, "unknown")
    self.assertEqual(post_clicks, 1, "Must NEVER re-click Post when confirmation timed out after click_post()")

  async def test_pre_click_failure_is_confirmed_failure_and_can_retry(self) -> None:
    """Failures before click_post() have outcome 'confirmed_failure' and are retried by retry_upload."""
    attempts = 0

    class MockPreClickFailDOM:
      async def dismiss_all_popups(self): pass
      async def upload_file(self, fp):
        nonlocal attempts
        attempts += 1
      async def wait_upload_complete(self, timeout=120):
        return False

    uploader = Uploader(MockPreClickFailDOM(), self.logger)
    orig_sleep = asyncio.sleep
    async def fast_sleep(sec):
      await orig_sleep(0.01)
    asyncio.sleep = fast_sleep
    try:
      task = UploadTask(file_path=Path("vid_fail.mp4"), caption="test")
      result = await uploader.retry_upload(task, max_retries=3)
    finally:
      asyncio.sleep = orig_sleep

    self.assertFalse(result.success)
    self.assertEqual(result.outcome, "confirmed_failure")
    self.assertEqual(attempts, 3)


class TestGUIIsolationHistoryAndScheduler(unittest.TestCase):
  """Regression tests for Priorities 2, 3, 4, 5 and optional caption prefix."""

  @classmethod
  def setUpClass(cls) -> None:
    cls.app = QApplication.instance() or QApplication(sys.argv)
    cls.app.setStyle("Fusion")

  def setUp(self) -> None:
    self.temp_dir = Path(tempfile.mkdtemp(prefix="tks_regtest_"))
    self.cookies_dir = self.temp_dir / "cookies"
    self.storage_dir = self.temp_dir / "storage"
    self.videos_dir = self.temp_dir / "videos"
    self.cookies_dir.mkdir(parents=True, exist_ok=True)
    self.storage_dir.mkdir(parents=True, exist_ok=True)
    self.videos_dir.mkdir(parents=True, exist_ok=True)

    config_path = project_root / "config.json"
    self.config = ConfigManager(config_path)
    self.theme_manager = ThemeManager(
      app=self.app,
      initial_mode=self.config.theme,
      accent_color=self.config.primary_color,
    )
    self.window = MainWindow(theme_manager=self.theme_manager)
    self.controller = GUIController(self.window, self.config, project_root)

    # Redirect controller to isolated temporary directories
    self.controller._cookies_dir = self.cookies_dir
    self.controller._cookie_manager._cookies_dir = self.cookies_dir
    self.controller._storage_service._storage_dir = self.storage_dir
    self.controller._storage_service._schedules_dir = self.storage_dir / "schedules"
    self.controller._storage_service._publishes_dir = self.storage_dir / "publishes"
    self.controller._storage_dir = self.storage_dir
    self.controller._schedules_dir = self.storage_dir / "schedules"
    self.controller._publishes_dir = self.storage_dir / "publishes"

    dummy_cookie = '[{"name": "sessionid", "value": "REDACTED", "domain": ".tiktok.com", "path": "/"}]'
    for acc in ["conta_alfa", "conta_beta"]:
      (self.cookies_dir / f"@{acc}-cookie.json").write_text(dummy_cookie, encoding="utf-8")

    for vname in ["vid1.mp4", "vid10.mp4", "vid100.mp4", "clip_part1.mp4", "clip_part2.mp4"]:
      (self.videos_dir / vname).write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 256)

    self.controller._load_accounts()
    self.controller._save_folder_path(str(self.videos_dir))
    self.window.set_wizard_step(0)
    self.controller._tasks = []
    self.controller._videos = []
    self.controller._per_video_meta = {}
    self.controller._studio_schedules = {}
    self.controller._studio_visibilities = {}
    self.window.folder_dropdown.setCurrentText(str(self.videos_dir))

  def tearDown(self) -> None:
    self.window.close()
    shutil.rmtree(self.temp_dir, ignore_errors=True)

  def test_past_due_schedule_is_marked_elapsed_unverified_and_not_migrated(self) -> None:
    """Priority 3: Elapsed scheduled items must NOT be moved to published and must stay blocked."""
    past_dt = datetime.now() - timedelta(hours=2)
    self.controller._storage_service.save_scheduled("conta_alfa", {
      "uploads": [{
        "file": "vid1.mp4",
        "caption": "test",
        "schedule_time": DateTimeUtils.format_iso(past_dt),
        "status": "success",
        "timestamp": int(past_dt.timestamp()),
        "video_id": None,
        "cm": False,
        "qc": "OK",
      }]
    })
    self.window.account_dropdown.setCurrentText("conta_alfa")
    self.controller._on_scan_clicked()
    self.app.processEvents()

    # Verify it was NOT migrated to publishes/
    pub_data = self.controller._storage_service.load_published("conta_alfa")
    self.assertEqual(pub_data["published"], [])

    # Verify status in table is 'Elapsed (Unverified)' and it is excluded from _get_selected_videos()
    statuses = {
      self.window.video_table.item(r, 1).text(): self.window.video_table.item(r, 5).text()
      for r in range(self.window.video_table.rowCount())
    }
    self.assertEqual(statuses["vid1.mp4"], "Elapsed (Unverified)")
    selected = [v.filename for v in self.controller._get_selected_videos()]
    self.assertNotIn("vid1.mp4", selected)

  def test_no_filename_prefix_collision_between_vid1_vid10_vid100_and_clips(self) -> None:
    """Priority 2: vid1 must not collide with vid10/vid100, and clip_part1 must not collide with clip_part2."""
    future_dt = datetime.now() + timedelta(hours=3)
    self.controller._storage_service.save_published("conta_alfa", {
      "published": ["vid1|2026-11-18T10:00:00"]
    })
    self.controller._storage_service.save_scheduled("conta_alfa", {
      "uploads": [{
        "file": "clip_part1.mp4",
        "caption": "test",
        "schedule_time": DateTimeUtils.format_iso(future_dt),
        "status": "success",
        "timestamp": int(future_dt.timestamp()),
        "video_id": None,
        "cm": False,
        "qc": "OK",
      }]
    })

    self.window.account_dropdown.setCurrentText("conta_alfa")
    self.controller._on_scan_clicked()
    self.app.processEvents()

    statuses = {}
    schedules = {}
    for r in range(self.window.video_table.rowCount()):
      fname = self.window.video_table.item(r, 1).text()
      statuses[fname] = self.window.video_table.item(r, 5).text()
      schedules[fname] = self.window.video_table.item(r, 3).text()

    self.assertEqual(statuses["vid1.mp4"], "Published")
    self.assertEqual(statuses["vid10.mp4"], "Pending")
    self.assertEqual(statuses["vid100.mp4"], "Pending")
    self.assertEqual(statuses["clip_part1.mp4"], "Scheduled")
    self.assertEqual(statuses["clip_part2.mp4"], "Pending")
    self.assertEqual(schedules["clip_part2.mp4"], "-")

  def test_account_switch_refreshes_table_and_worker_binds_original_account(self) -> None:
    """Priority 2: Switching account refreshes table automatically, and worker writes to its bound account."""
    future_dt = datetime.now() + timedelta(hours=3)
    self.controller._storage_service.save_scheduled("conta_alfa", {
      "uploads": [{
        "file": "vid1.mp4",
        "caption": "test",
        "schedule_time": DateTimeUtils.format_iso(future_dt),
        "status": "success",
        "timestamp": int(future_dt.timestamp()),
      }]
    })
    self.window.account_dropdown.setCurrentText("conta_alfa")
    self.controller._on_scan_clicked()
    self.app.processEvents()

    # Now switch to conta_beta without clicking Scan manually
    self.window.account_dropdown.setCurrentText("conta_beta")
    self.app.processEvents()

    statuses_beta = {
      self.window.video_table.item(r, 1).text(): self.window.video_table.item(r, 5).text()
      for r in range(self.window.video_table.rowCount())
    }
    self.assertEqual(self.controller._cached_username, "conta_beta")
    self.assertEqual(statuses_beta["vid1.mp4"], "Pending", "vid1.mp4 must be Pending on conta_beta")

    # Verify set_upload_running(True) disables Accounts tab action buttons too
    self.window.set_upload_running(True)
    self.assertFalse(self.window.account_dropdown.isEnabled())
    self.assertFalse(self.window.accounts_random_btn.isEnabled())
    self.assertFalse(self.window.add_account_btn.isEnabled())
    self.assertFalse(self.window.accounts_edit_btn.isEnabled())
    self.assertFalse(self.window.accounts_delete_btn.isEnabled())
    self.window.set_upload_running(False)

    # Verify _on_upload_complete saves to worker.username even if dropdown text differs
    self.controller._tasks = [UploadTask(file_path=self.videos_dir / "vid10.mp4", caption="test", schedule_time=future_dt)]
    class BoundWorker:
      username = "conta_alfa"
      results = [UploadResult(success=True, file_path=self.videos_dir / "vid10.mp4", message="OK", timestamp=datetime.now())]
    self.controller._worker = BoundWorker()
    self.controller._on_upload_complete(True, "vid10.mp4")

    alfa_uploads = [u["file"] for u in self.controller._storage_service.load_scheduled("conta_alfa")["uploads"]]
    beta_uploads = [u["file"] for u in self.controller._storage_service.load_scheduled("conta_beta")["uploads"]]
    self.assertIn("vid10.mp4", alfa_uploads)
    self.assertNotIn("vid10.mp4", beta_uploads)

  def test_confirmed_failure_can_be_retried_while_unknown_stays_blocked(self) -> None:
    """Priority 1 & 2: Confirmed 'failed' items can be re-selected, while 'unknown' items are blocked."""
    now_dt = datetime.now()
    self.controller._storage_service.save_scheduled("conta_beta", {
      "uploads": [
        {
          "file": "vid1.mp4",
          "caption": "test",
          "schedule_time": None,
          "status": "unknown",
          "outcome": "unknown",
          "timestamp": int(now_dt.timestamp()),
        },
        {
          "file": "vid10.mp4",
          "caption": "test",
          "schedule_time": None,
          "status": "failed",
          "outcome": "confirmed_failure",
          "timestamp": int(now_dt.timestamp()),
        },
      ]
    })
    self.window.account_dropdown.setCurrentText("conta_beta")
    self.controller._on_scan_clicked()
    self.app.processEvents()

    statuses = {
      self.window.video_table.item(r, 1).text(): self.window.video_table.item(r, 5).text()
      for r in range(self.window.video_table.rowCount())
    }
    self.assertEqual(statuses["vid1.mp4"], "Unknown")
    self.assertEqual(statuses["vid10.mp4"], "Failed")

    selected = [v.filename for v in self.controller._get_selected_videos()]
    self.assertNotIn("vid1.mp4", selected, "Unknown outcome video must NEVER be auto-selected for retry")
    self.assertIn("vid10.mp4", selected, "Confirmed failed video can be selected for retry without deleting history")

  def test_multiday_scheduler_window_daily_limit_and_conflict_filtering(self) -> None:
    """Priority 4: Multi-day schedule respects time window on all days, daily_limit, and existing conflicts."""
    base_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    end_day = base_day + timedelta(days=2)

    cfg = ScheduleConfig(
      start_date=base_day.replace(hour=9, minute=0),
      end_date=end_day.replace(hour=18, minute=0),
      interval_minutes=180,
      daily_limit=2,
      time_window_start=(9, 0),
      time_window_end=(18, 0),
    )
    slots = self.controller._scheduler.generate_slots(cfg)
    # 3 days * 2 daily_limit = 6 slots total, all between 09:00 and 18:00
    self.assertEqual(len(slots), 6)
    for s in slots:
      self.assertGreaterEqual(s.hour, 9)
      self.assertLessEqual(s.hour, 18)

  def test_caption_prefix_is_optional_and_disabled_by_default(self) -> None:
    """Caption requirement: 'Cre: <videoid>' prefix is disabled by default and sends exact user caption."""
    self.assertFalse(self.window.prefix_caption_check.isChecked())
    exact_caption = "Minha legenda personalizada #teste #tiktok"
    built_default = self.controller._build_caption(
      Path("vid10_promo.mp4"),
      exact_caption,
      include_prefix=self.window.prefix_caption_check.isChecked(),
    )
    self.assertEqual(built_default, exact_caption)

    built_with_prefix = self.controller._build_caption(
      Path("vid10_promo.mp4"),
      exact_caption,
      include_prefix=True,
    )
    self.assertEqual(built_with_prefix, f"Cre: vid10\n{exact_caption}")

  def test_setup_chromium_check_verifies_file_exists(self) -> None:
    """Priority 5: setup.check_playwright_chromium() verifies binary exists on disk."""
    self.assertTrue(setup_module.check_playwright_chromium())

  def test_execute_button_stays_enabled_when_validation_timer_ticks(self) -> None:
    """Execute button Bug Fix: start_btn must NOT be disabled by _validate_time_selection when _tasks already exist."""
    self.window.account_dropdown.setCurrentText("conta_alfa")
    self.controller._on_scan_clicked()
    self.controller._on_generate_schedule()
    self.app.processEvents()
    self.assertTrue(self.window.start_btn.isEnabled())
    self.assertGreater(len(self.controller._tasks), 0)

    # Simulate the start_time dropdown becoming < now + 15min as the clock advances
    self.window.set_actions_enabled(False, has_tasks=bool(self.controller._tasks))
    self.assertFalse(self.window.generate_btn.isEnabled())
    self.assertTrue(
      self.window.start_btn.isEnabled(),
      "Execute (start_btn) must stay enabled once tasks have been generated!",
    )

  def test_logs_button_opens_logs_dialog_and_clear_view_preserves_file(self) -> None:
    """Logs button Bug Fix: clicking Logs opens LogsDialog, receives logs, and Clear View does not delete persistent file."""
    self.controller._logger.info("Test log entry for LogsDialog")
    self.app.processEvents()

    self.window.toggle_log_btn.click()
    self.app.processEvents()

    self.assertIsNotNone(self.window._logs_dialog)
    self.assertTrue(self.window._logs_dialog.isVisible())
    self.assertGreater(len(self.window._logs_dialog._entries), 0)

    # Clear view only and verify persistent file still exists
    self.window._logs_dialog.clear_view_only()
    self.assertEqual(len(self.window._logs_dialog._entries), 0)
    self.assertTrue(self.controller._log_file.exists())

    # Reload persistent history
    self.window._logs_dialog.load_persistent_history()
    self.assertGreater(len(self.window._logs_dialog._entries), 0)
    self.window._logs_dialog.hide()

  def test_pause_resume_and_stop_preserve_remaining_queue(self) -> None:
    """Pause/Stop Bug Fix: Stop preserves remaining unprocessed tasks in self._tasks and re-enables Execute."""
    self.window.account_dropdown.setCurrentText("conta_alfa")
    self.controller._on_scan_clicked()
    self.window.limit_spin.setValue(3)
    self.controller._on_generate_schedule()
    self.app.processEvents()
    self.assertEqual(len(self.controller._tasks), 3)

    first_task = self.controller._tasks[0]
    future_dt = datetime.now() + timedelta(hours=2)

    class MockStoppableWorker:
      username = "conta_alfa"
      _stop_flag = False
      is_paused = False
      results = [
        UploadResult(
          success=True,
          file_path=first_task.file_path,
          message="OK",
          timestamp=datetime.now(),
        )
      ]
      def isRunning(self):
        return False
      def toggle_pause(self):
        self.is_paused = not self.is_paused
      def request_stop(self):
        self._stop_flag = True

    self.controller._worker = MockStoppableWorker()
    self.window.set_upload_running(True)

    # Test Pause / Resume toggle
    self.controller._on_pause_resume()
    self.assertTrue(self.controller._worker.is_paused)
    self.assertIn("Resume", self.window.pause_btn.text())

    self.controller._on_pause_resume()
    self.assertFalse(self.controller._worker.is_paused)
    self.assertIn("Pause", self.window.pause_btn.text())

    # Simulate 1st video completing, then user clicking Stop
    self.controller._on_upload_complete(True, first_task.file_path.name)
    self.controller._on_stop_clicked()
    self.assertTrue(self.controller._worker._stop_flag)
    self.controller._on_finished()
    self.app.processEvents()

    # 1st task was completed; 2 remaining tasks must still be in self._tasks and start_btn must be enabled!
    self.assertEqual(len(self.controller._tasks), 2)
    self.assertNotIn(first_task.file_path.name, [t.file_path.name for t in self.controller._tasks])
    self.assertTrue(self.window.start_btn.isEnabled(), "Execute must stay enabled to resume the remaining 2 tasks after Stop!")

  def test_wizard_tiktok_studio_flow_and_back_preserves_state(self) -> None:
    """TKS 2.0 Studio: Navigating between Account, TikTok Studio, and Execution preserves state."""
    self.assertEqual(self.window.current_wizard_step(), 0)

    # Step 1: Select account card -> automatically advances to Studio (index 1)
    self.controller._on_account_card_selected("conta_alfa")
    self.app.processEvents()
    self.assertEqual(self.window.current_wizard_step(), 1)
    self.assertEqual(self.window.account_dropdown.currentText(), "conta_alfa")

    # Step 2: Empty Studio shows DropZone with red upload button (Image 1)
    self.assertEqual(self.window.studio_page.stack.currentIndex(), 0)
    self.assertFalse(self.window.studio_page.publish_btn.isEnabled())

    # Load 3 videos -> Studio switches to table state (Image 2)
    v_paths = [
      str(self.videos_dir / "vid1.mp4"),
      str(self.videos_dir / "vid10.mp4"),
      str(self.videos_dir / "vid100.mp4"),
    ]
    self.controller._on_files_dropped(v_paths)
    self.app.processEvents()
    self.assertEqual(len(self.controller._videos), 3)
    self.assertEqual(self.window.studio_page.stack.currentIndex(), 1)
    self.assertTrue(self.window.studio_page.publish_btn.isEnabled())
    self.assertIn("Publicar (3)", self.window.studio_page.publish_btn.text())

    # Edit caption inline for vid10.mp4 (Image 4)
    self.controller._on_studio_caption_updated("vid10.mp4", "Legenda viral no TikTok #foryou")
    self.assertEqual(self.controller._per_video_meta["vid10.mp4"]["caption"], "Legenda viral no TikTok #foryou")

    # Set schedule date/time for vid1.mp4 (Image 3)
    sched_dt = datetime.now() + timedelta(days=2, hours=3)
    self.controller._on_studio_schedule_updated("vid1.mp4", sched_dt)
    self.assertEqual(self.controller._studio_schedules["vid1.mp4"], sched_dt)

    # Click Publicar (3) -> opens Publications tab and starts execution directly
    with patch.object(self.controller, "_on_start_upload") as mock_start:
      self.controller._on_studio_publish_clicked()
      self.app.processEvents()
      self.assertEqual(self.window.studio_page.stack.currentIndex(), 2, "Must show Publicações tab")
      self.assertEqual(len(self.controller._tasks), 3)
      self.assertEqual(self.controller._tasks[1].caption, "Legenda viral no TikTok #foryou")
      self.assertEqual(self.controller._tasks[0].schedule_time, sched_dt)
      mock_start.assert_called_once()

    # Go back to Studio upload and verify state is intact
    self.window.studio_page.show_upload()
    self.assertEqual(len(self.controller._videos), 3)
    self.assertEqual(self.controller._per_video_meta["vid10.mp4"]["caption"], "Legenda viral no TikTok #foryou")

  def test_wizard_smart_distribution_10_videos_5_times_2_days(self) -> None:
    """TKS 2.0 Wizard: 10 videos distributed across 5 daily times over 2 selected days produces 10 ordered tasks."""
    self.controller._on_clear_loaded_videos()
    ten_paths = []
    for i in range(1, 11):
      vp = self.videos_dir / f"batch_{i:02d}.mp4"
      vp.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 256)
      ten_paths.append(str(vp))

    self.window.account_dropdown.setCurrentText("conta_beta")
    self.controller._add_video_paths(ten_paths)
    self.window.limit_spin.setMaximum(10)
    self.window.limit_spin.setValue(10)

    day1 = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    day2 = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    self.window.config_page.set_specific_dates([day1, day2])
    self.window.config_page.set_time_slots(["09:00", "12:00", "15:00", "18:00", "21:00"])

    self.controller._on_wizard_distribute()
    self.app.processEvents()

    self.assertEqual(len(self.controller._tasks), 10)
    self.assertEqual(self.controller._tasks[0].file_path.name, "batch_01.mp4")
    self.assertEqual(self.controller._tasks[9].file_path.name, "batch_10.mp4")
    day1_count = sum(1 for t in self.controller._tasks if t.schedule_time.strftime("%Y-%m-%d") == day1)
    day2_count = sum(1 for t in self.controller._tasks if t.schedule_time.strftime("%Y-%m-%d") == day2)
    self.assertEqual(day1_count, 5)
    self.assertEqual(day2_count, 5)

  def test_wizard_state_persistence_and_restore_after_restart(self) -> None:
    """TKS 2.0 Studio: Closing and reopening restores account, loaded videos, studio captions, tasks, and step."""
    self.window.account_dropdown.setCurrentText("conta_alfa")
    self.controller._on_clear_loaded_videos()
    v_paths = [str(self.videos_dir / "vid1.mp4"), str(self.videos_dir / "vid10.mp4")]
    self.controller._add_video_paths(v_paths)
    self.controller._on_studio_caption_updated("vid1.mp4", "Persistida 1")
    with patch.object(self.controller, "_on_start_upload"):
      self.controller._on_studio_publish_clicked()
      self.assertEqual(self.window.studio_page.stack.currentIndex(), 2)
      self.controller._save_wizard_state()

    # Simulate app restart on a fresh controller state pointing to the same storage dir
    self.controller._videos.clear()
    self.controller._tasks.clear()
    self.controller._per_video_meta.clear()
    self.window.set_wizard_step(0)

    self.controller._restore_wizard_state()
    self.app.processEvents()

    self.assertEqual(self.window.account_dropdown.currentText(), "conta_alfa")
    self.assertEqual(len(self.controller._videos), 2)
    self.assertEqual(len(self.controller._tasks), 2)
    self.assertEqual(self.controller._per_video_meta.get("vid1.mp4", {}).get("caption"), "Persistida 1")


if __name__ == "__main__":
  unittest.main(verbosity=2)
