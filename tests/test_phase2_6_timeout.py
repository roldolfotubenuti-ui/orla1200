import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core.config_manager import ConfigManager
from core.dom_handler import DOMHandler
from core.schedule_rule_engine import ScheduleRuleEngine
from utils.datetime_utils import DateTimeUtils


class TestPhase26DynamicTimeout(unittest.IsolatedAsyncioTestCase):
  """Tests for Phase 2.6: Dynamic timeout, 30m rule, and DOM schedule error detection."""

  def setUp(self):
    self.page_mock = AsyncMock()
    self.logger_mock = MagicMock()
    self.dom_handler = DOMHandler(self.page_mock, self.logger_mock, DateTimeUtils)

  async def test_button_enabled_early_at_8s(self):
    """Button enables at 8s -> check_content_quality exits immediately without waiting 45s."""
    call_count = 0

    async def mock_is_button_enabled():
      nonlocal call_count
      call_count += 1
      # 1st call at start, then poll every 1.5s -> by 5th call ~6-8s
      return call_count >= 5

    async def mock_evaluate(script):
      if call_count >= 5:
        return "status-success"
      return "status-checking"

    self.dom_handler.is_post_button_enabled = mock_is_button_enabled
    self.page_mock.evaluate = mock_evaluate

    with patch("asyncio.sleep", new_callable=AsyncMock):
      result = await self.dom_handler.check_content_quality(max_wait_seconds=45)

    self.assertIn(result["state"], ["passed", "ready", "success", "checking"])
    self.assertFalse(result.get("content_check_timeout", False))
    self.assertIsNotNone(result.get("button_enable_wait_sec"))
    self.assertLess(call_count, 15)  # Definitely didn't poll all 30 times (45s / 1.5s)

  async def test_button_enabled_at_20s(self):
    """Button enables around 20s (~14 polls) -> exits promptly."""
    call_count = 0

    async def mock_is_button_enabled():
      nonlocal call_count
      call_count += 1
      return call_count >= 14

    self.dom_handler.is_post_button_enabled = mock_is_button_enabled
    self.page_mock.evaluate = AsyncMock(return_value="status-success")

    with patch("asyncio.sleep", new_callable=AsyncMock):
      result = await self.dom_handler.check_content_quality(max_wait_seconds=45)

    self.assertIn(result["state"], ["passed", "ready", "success"])
    self.assertFalse(result.get("content_check_timeout", False))
    self.assertLess(call_count, 25)

  async def test_button_enabled_at_35s(self):
    """Button enables around 35s (~24 polls) -> completes successfully."""
    call_count = 0

    async def mock_is_button_enabled():
      nonlocal call_count
      call_count += 1
      return call_count >= 24

    self.dom_handler.is_post_button_enabled = mock_is_button_enabled
    self.page_mock.evaluate = AsyncMock(return_value="status-success")

    with patch("asyncio.sleep", new_callable=AsyncMock):
      result = await self.dom_handler.check_content_quality(max_wait_seconds=45)

    self.assertIn(result["state"], ["passed", "ready", "success"])
    self.assertFalse(result.get("content_check_timeout", False))

  async def test_button_still_disabled_after_45s_timeout(self):
    """Button never enables after 45s -> reports timeout and diagnosis."""
    self.dom_handler.is_post_button_enabled = AsyncMock(return_value=False)
    self.dom_handler.diagnose_disabled_button = AsyncMock(return_value={"error_detected": "Cover photo not ready"})
    self.page_mock.evaluate = AsyncMock(return_value="status-checking")

    with patch("asyncio.sleep", new_callable=AsyncMock):
      result = await self.dom_handler.check_content_quality(max_wait_seconds=45)

    self.assertEqual(result["state"], "button_disabled")
    self.assertTrue(result["content_check_timeout"])
    self.assertIn("Cover photo not ready", result.get("message", ""))

  async def test_verify_schedule_inputs_detects_all_error_patterns(self):
    """verify_schedule_inputs detects 15, 20, 25, 30 min, and other DOM error messages."""
    test_cases = [
      ("Escolha um horário entre 30 min e 10 dias", True),
      ("Escolha um horário entre 25 min e 10 dias a partir de agora", True),
      ("Choose a time between 30 min and 10 days", True),
      ("Horário inválido selecionado", True),
      ("Data inválida para agendamento", True),
      ("Limite máximo de 10 dias excedido", True),
    ]

    for error_text, should_catch in test_cases:
      self.page_mock.evaluate = AsyncMock(return_value={
        "timeVal": "10:00",
        "dateVal": "2026-11-20",
        "errorMsg": error_text,
        "hasErrorStyle": False,
      })
      res = await self.dom_handler.verify_schedule_inputs(10, 0, 20, "Novembro")
      self.assertFalse(res["valid"], f"Failed to detect error in: {error_text}")
      self.assertIn(error_text, res["reason"])

  def test_30_minute_rule_in_datetime_utils(self):
    """DateTimeUtils enforces 30 minutes minimum offset."""
    now = datetime.now()
    # 20 min ahead -> Invalid
    dt_20 = now + timedelta(minutes=20)
    self.assertFalse(DateTimeUtils.is_valid_schedule_time(dt_20))

    # 28 min ahead -> Invalid under 30m rule
    dt_28 = now + timedelta(minutes=28)
    self.assertFalse(DateTimeUtils.is_valid_schedule_time(dt_28))

    # 35 min ahead -> Valid
    dt_35 = now + timedelta(minutes=35)
    self.assertTrue(DateTimeUtils.is_valid_schedule_time(dt_35))

  def test_30_minute_rule_in_schedule_rule_engine(self):
    """ScheduleRuleEngine default is 30 minutes."""
    config_mock = MagicMock()
    config_mock.min_offset_minutes = 30
    config_mock.max_offset_days = 10
    config_mock.max_offset_months = 1
    config_mock.minute_step = 5
    engine = ScheduleRuleEngine(config_mock)
    self.assertEqual(engine.min_offset_minutes, 30)

    now = datetime(2026, 11, 20, 10, 0, 0)  # Reference time on boundary
    # 25 min -> invalid in engine (< 30 min)
    dt_25 = now + timedelta(minutes=25)
    valid, reason = engine.validate(dt_25, now=now)
    self.assertFalse(valid)
    self.assertIn("30", reason)

    # 35 min -> valid
    dt_35 = now + timedelta(minutes=35)
    valid, reason = engine.validate(dt_35, now=now)
    self.assertTrue(valid)


if __name__ == "__main__":
  unittest.main()
