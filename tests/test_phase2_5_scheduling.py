from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.config_manager import ConfigManager
from core.dom_handler import DOMHandler, SelectorError
from core.schedule_rule_engine import ScheduleRuleEngine
from core.scheduler import UploadTask
from core.uploader import Uploader
from gui.controllers.upload_worker import UploadWorker
from gui.controllers.uploads import UploadExecutionControllerMixin
from utils.datetime_utils import DateTimeUtils


class TestPhase25Scheduling(unittest.TestCase):
  """Comprehensive test suite for Phase 2.5: Smart Scheduling Correction."""

  def setUp(self) -> None:
    self.temp_dir = Path(tempfile.mkdtemp())
    self.config_path = self.temp_dir / "config.json"
    cfg_data = {
      "scheduleRules": {
        "minOffsetMinutes": 25,
        "maxOffsetDays": 10,
        "minuteStep": 5,
      },
      "paths": {
        "storageDir": str(self.temp_dir / "storage"),
        "cookiesDir": str(self.temp_dir / "cookies"),
      },
    }
    with open(self.config_path, "w", encoding="utf-8") as f:
      json.dump(cfg_data, f)

    self.config = ConfigManager(self.config_path)
    self.rule_engine = ScheduleRuleEngine(self.config)
    self.logger = MagicMock()

  def tearDown(self) -> None:
    shutil.rmtree(self.temp_dir, ignore_errors=True)

  # ------------------------------------------------------------------
  # Test 1: All valid schedules
  # ------------------------------------------------------------------
  def test_01_all_valid_schedules(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Caption 1", schedule_time=now + timedelta(minutes=30)),
      UploadTask(Path("vid2.mp4"), "Caption 2", schedule_time=now + timedelta(minutes=60)),
      UploadTask(Path("vid3.mp4"), "Caption 3", schedule_time=now + timedelta(minutes=90)),
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertTrue(insp["is_valid"])
    self.assertEqual(len(insp["issues"]), 0)
    self.assertEqual(insp["scheduled_count"], 3)
    self.assertEqual(insp["immediate_count"], 0)

  # ------------------------------------------------------------------
  # Test 2: One expired schedule
  # ------------------------------------------------------------------
  def test_02_single_expired_schedule(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Caption 1", schedule_time=now - timedelta(minutes=5)),  # Expired
      UploadTask(Path("vid2.mp4"), "Caption 2", schedule_time=now + timedelta(minutes=60)),
      UploadTask(Path("vid3.mp4"), "Caption 3", schedule_time=now + timedelta(minutes=90)),
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertFalse(insp["is_valid"])
    self.assertEqual(len(insp["issues"]), 1)
    self.assertEqual(insp["issues"][0]["filename"], "vid1.mp4")
    self.assertEqual(insp["issues"][0]["issue_type"], "expired")

    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=30, now=now)
    self.assertEqual(len(recalc), 3)
    # vid1.mp4 should now be at least now + 25m (rounded up -> 10:25)
    self.assertEqual(recalc[0]["new_schedule"], datetime(2026, 11, 19, 10, 25, 0))
    self.assertEqual(recalc[1]["new_schedule"], datetime(2026, 11, 19, 10, 55, 0))
    self.assertEqual(recalc[2]["new_schedule"], datetime(2026, 11, 19, 11, 25, 0))

  # ------------------------------------------------------------------
  # Test 3: All expired schedules
  # ------------------------------------------------------------------
  def test_03_all_expired_schedules(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    yesterday = now - timedelta(days=1)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Cap 1", schedule_time=yesterday.replace(hour=14, minute=0)),
      UploadTask(Path("vid2.mp4"), "Cap 2", schedule_time=yesterday.replace(hour=14, minute=30)),
      UploadTask(Path("vid3.mp4"), "Cap 3", schedule_time=yesterday.replace(hour=15, minute=0)),
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertFalse(insp["is_valid"])
    self.assertEqual(len(insp["issues"]), 3)

    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=30, now=now)
    times = [r["new_schedule"] for r in recalc]
    # Verify all times are distinct and sequential
    self.assertEqual(len(set(times)), 3)
    self.assertTrue(times[0] < times[1] < times[2])
    self.assertTrue(times[0] >= now + timedelta(minutes=25))

  # ------------------------------------------------------------------
  # Test 4: Multiple expired / near-present schedules
  # ------------------------------------------------------------------
  def test_04_multiple_expired_schedules(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Cap 1", schedule_time=now + timedelta(minutes=5)),   # Insufficient lead
      UploadTask(Path("vid2.mp4"), "Cap 2", schedule_time=now + timedelta(minutes=10)),  # Insufficient lead
      UploadTask(Path("vid3.mp4"), "Cap 3", schedule_time=now - timedelta(hours=2)),     # In past
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertFalse(insp["is_valid"])
    self.assertEqual(len(insp["issues"]), 3)

    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=15, now=now)
    self.assertEqual(recalc[0]["new_schedule"], datetime(2026, 11, 19, 10, 25, 0))
    self.assertEqual(recalc[1]["new_schedule"], datetime(2026, 11, 19, 10, 40, 0))
    self.assertEqual(recalc[2]["new_schedule"], datetime(2026, 11, 19, 10, 55, 0))

  # ------------------------------------------------------------------
  # Test 5: Duplicate schedules
  # ------------------------------------------------------------------
  def test_05_duplicate_schedules(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    same_time = now + timedelta(minutes=30)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Cap 1", schedule_time=same_time),
      UploadTask(Path("vid2.mp4"), "Cap 2", schedule_time=same_time),
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertFalse(insp["is_valid"])
    issue_types = [iss["issue_type"] for iss in insp["issues"]]
    self.assertIn("duplicate", issue_types)

    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=30, now=now)
    self.assertNotEqual(recalc[0]["new_schedule"], recalc[1]["new_schedule"])
    self.assertEqual(recalc[1]["new_schedule"] - recalc[0]["new_schedule"], timedelta(minutes=30))

  # ------------------------------------------------------------------
  # Test 6: Interval of 15 minutes
  # ------------------------------------------------------------------
  def test_06_interval_15_minutes(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Cap 1", schedule_time=now),
      UploadTask(Path("vid2.mp4"), "Cap 2", schedule_time=now),
    ]
    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=15, now=now)
    delta = recalc[1]["new_schedule"] - recalc[0]["new_schedule"]
    self.assertEqual(delta, timedelta(minutes=15))

  # ------------------------------------------------------------------
  # Test 7: Interval of 30 minutes
  # ------------------------------------------------------------------
  def test_07_interval_30_minutes(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    tasks = [
      UploadTask(Path("vid1.mp4"), "Cap 1", schedule_time=now),
      UploadTask(Path("vid2.mp4"), "Cap 2", schedule_time=now),
    ]
    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=30, now=now)
    delta = recalc[1]["new_schedule"] - recalc[0]["new_schedule"]
    self.assertEqual(delta, timedelta(minutes=30))

  # ------------------------------------------------------------------
  # Test 8: Minimum lead time of 25 minutes
  # ------------------------------------------------------------------
  def test_08_minimum_lead_time_25_minutes(self) -> None:
    now = datetime(2026, 11, 19, 10, 1, 0)
    min_allowed = self.rule_engine.min_allowed_datetime(now)
    # 10:01 + 25m = 10:26 -> round up to next 5-min step = 10:30
    self.assertEqual(min_allowed, datetime(2026, 11, 19, 10, 30, 0))
    self.assertTrue((min_allowed - now).total_seconds() >= 25 * 60)

    # 10:20 (only 19 min lead time) must be rejected
    valid, reason = self.rule_engine.validate(now + timedelta(minutes=19), now=now)
    self.assertFalse(valid)
    self.assertIn("at least 25 min", reason)

  # ------------------------------------------------------------------
  # Test 9: Maximum scheduling limit (10 days)
  # ------------------------------------------------------------------
  def test_09_maximum_limit_10_days(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    max_dt = self.rule_engine.max_allowed_datetime(now)
    self.assertEqual(max_dt, now + timedelta(days=10))

    # Day 11 must be rejected
    beyond = now + timedelta(days=11)
    valid, reason = self.rule_engine.validate(beyond, now=now)
    self.assertFalse(valid)
    self.assertIn("10 day(s)", reason)

    # Day 5 must be accepted
    within = now + timedelta(days=5, hours=2)
    within = within.replace(minute=0, second=0, microsecond=0)
    valid, _ = self.rule_engine.validate(within, now=now)
    self.assertTrue(valid)

  # ------------------------------------------------------------------
  # Test 10: Restored queue from previous execution
  # ------------------------------------------------------------------
  def test_10_restored_queue_from_previous_run(self) -> None:
    now = datetime.now()
    # Simulate tasks restored from wizard-state.json saved 5 hours ago
    past_time = now - timedelta(hours=5)
    tasks = [
      UploadTask(Path("vid_restored.mp4"), "Restored caption", schedule_time=past_time),
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertFalse(insp["is_valid"])
    self.assertEqual(insp["issues"][0]["issue_type"], "expired")

  # ------------------------------------------------------------------
  # Test 11: UI and task synchronization on approved recalculation
  # ------------------------------------------------------------------
  def test_11_ui_synchronization_and_history(self) -> None:
    now = datetime.now()
    old_time = now - timedelta(hours=1)
    new_time = now + timedelta(minutes=30)
    new_time = new_time.replace(second=0, microsecond=0)

    task = UploadTask(Path("sync_vid.mp4"), "Sync Cap", schedule_time=old_time)
    recalculated = [
      {
        "task": task,
        "filename": "sync_vid.mp4",
        "old_schedule": old_time,
        "new_schedule": new_time,
        "changed": True,
        "reason": "Vencido",
      }
    ]

    # Create dummy controller using UploadExecutionControllerMixin
    class DummyController(UploadExecutionControllerMixin):
      def __init__(self, storage_dir: str):
        self._tasks = [task]
        self._storage_dir = storage_dir
        self._studio_schedules = {"sync_vid.mp4": old_time}
        self._window = MagicMock()
        self._window.account_dropdown.currentText.return_value = "sync_user"
        self._logger = MagicMock()

    storage_dir = self.temp_dir / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    ctrl = DummyController(str(storage_dir))
    ctrl._apply_recalculated_schedule(recalculated)

    # 1. Task updated
    self.assertEqual(task.schedule_time, new_time)
    # 2. Studio schedule updated
    self.assertEqual(ctrl._studio_schedules["sync_vid.mp4"], new_time)
    # 3. History file created and logged
    hist_file = storage_dir / "schedule_history.json"
    self.assertTrue(hist_file.exists())
    with open(hist_file, "r", encoding="utf-8") as f:
      hist = json.load(f)
    self.assertEqual(len(hist), 1)
    self.assertEqual(hist[0]["filename"], "sync_vid.mp4")
    self.assertEqual(hist[0]["account"], "sync_user")

  # ------------------------------------------------------------------
  # Test 12: DOM schedule validation failure
  # ------------------------------------------------------------------
  def test_12_dom_validation_failure(self) -> None:
    async def run_async():
      mock_page = MagicMock()
      # Simulate evaluate returning error message from TikTok DOM
      mock_page.evaluate = AsyncMock(return_value={
        "timeVal": "07:35",
        "dateVal": "19/11/2026",
        "errorMsg": "Select a time that is at least 15 minutes from now",
        "hasErrorStyle": True,
      })
      dom = DOMHandler(mock_page, self.logger, DateTimeUtils())
      dom.is_post_button_enabled = AsyncMock(return_value=False)

      verification = await dom.verify_schedule_inputs("07", "35", 19, "November")
      self.assertFalse(verification["valid"])
      self.assertIn("at least 15 minutes", verification["reason"])

    asyncio.run(run_async())

  # ------------------------------------------------------------------
  # Test 13: Immediate publication
  # ------------------------------------------------------------------
  def test_13_immediate_publication(self) -> None:
    now = datetime(2026, 11, 19, 10, 0, 0)
    tasks = [
      UploadTask(Path("immediate.mp4"), "Immediate caption", schedule_time=None),
    ]
    insp = self.rule_engine.inspect_queue(tasks, now=now)
    self.assertTrue(insp["is_valid"])
    self.assertEqual(insp["immediate_count"], 1)
    self.assertEqual(insp["scheduled_count"], 0)

    recalc = self.rule_engine.recalculate_schedule_queue(tasks, interval_minutes=30, now=now)
    self.assertIsNone(recalc[0]["new_schedule"])
    self.assertFalse(recalc[0]["changed"])

  # ------------------------------------------------------------------
  # Test 14: Revalidation before submission in worker
  # ------------------------------------------------------------------
  def test_14_revalidation_before_submission(self) -> None:
    async def run_async():
      now = datetime.now()
      # Task has an expired schedule at execution time
      expired_task = UploadTask(
        file_path=Path("expired.mp4"),
        caption="Expired caption",
        schedule_time=now - timedelta(minutes=10),
      )
      worker = UploadWorker(
        cookie_manager=MagicMock(),
        username="test_user",
        tasks=[expired_task],
        headless=True,
        retry_enabled=False,
        logger=self.logger,
        rule_engine=self.rule_engine,
      )

      # Mock browser manager to ensure launch is not called if aborted
      with patch("gui.controllers.upload_worker.BrowserManager") as mock_bm_cls:
        mock_bm = MagicMock()
        mock_bm.launch = AsyncMock()
        mock_bm.close = AsyncMock()
        mock_bm.get_page = MagicMock()
        mock_bm_cls.return_value = mock_bm

        await worker._execute()

        # The task should fail with validation error and not call upload_video
        self.assertEqual(len(worker._results), 1)
        self.assertFalse(worker._results[0].success)
        self.assertIn("Schedule validation failed", worker._results[0].message)

    asyncio.run(run_async())


if __name__ == "__main__":
  unittest.main()
