from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from dateutil.relativedelta import relativedelta

from core.config_manager import ConfigManager


class ScheduleRuleEngine:
  """
  Single authoritative source for all TikTok scheduling constraints.

  Referenced by both GUI (for dynamic option filtering) and CLI/backend
  (for hard validation before Playwright submission).  All time
  calculations use **calendar month** offsets (Feb 17 -> Mar 17),
  not fixed day counts.

  :param config: Application configuration manager.
  :type config: ConfigManager
  """

  def __init__(self, config: ConfigManager) -> None:
    """
    Initialize ScheduleRuleEngine from config.

    :param config: ConfigManager providing rule parameters.
    :type config: ConfigManager
    """
    self._min_offset_minutes: int = getattr(config, "min_offset_minutes", 30)
    self._max_offset_days: int = getattr(config, "max_offset_days", 10)
    self._max_offset_months: int = getattr(config, "max_offset_months", 1)
    self._minute_step: int = getattr(config, "minute_step", 5)

  # ------------------------------------------------------------------
  # Properties
  # ------------------------------------------------------------------

  @property
  def min_offset_minutes(self) -> int:
    """
    Minimum future offset in minutes.

    :rtype: int
    """
    return self._min_offset_minutes

  @property
  def max_offset_days(self) -> int:
    """
    Maximum future offset in days (TikTok limit: 10 days).

    :rtype: int
    """
    return self._max_offset_days

  @property
  def max_offset_months(self) -> int:
    """
    Maximum future offset in calendar months.

    :rtype: int
    """
    return self._max_offset_months

  @property
  def minute_step(self) -> int:
    """
    Allowed minute granularity (step size).

    :rtype: int
    """
    return self._minute_step

  # ------------------------------------------------------------------
  # Boundary calculations
  # ------------------------------------------------------------------

  def min_allowed_datetime(self, now: datetime | None = None) -> datetime:
    """
    Earliest allowed schedule timestamp.

    :param now: Reference time (defaults to ``datetime.now()``).
    :type now: datetime | None
    :return: ``now + min_offset_minutes``, rounded up to the next
             valid minute step.
    :rtype: datetime
    """
    if now is None:
      now = datetime.now()
    raw = now + timedelta(minutes=self._min_offset_minutes)
    return self.round_minute_up(raw)

  def max_allowed_datetime(self, now: datetime | None = None) -> datetime:
    """
    Latest allowed schedule timestamp.

    TikTok officially limits scheduling to 10 days in advance.

    :param now: Reference time (defaults to ``datetime.now()``).
    :type now: datetime | None
    :return: ``now + max_offset_days`` (days).
    :rtype: datetime
    """
    if now is None:
      now = datetime.now()
    return now + timedelta(days=self._max_offset_days)

  # ------------------------------------------------------------------
  # Validation
  # ------------------------------------------------------------------

  def validate(
    self,
    dt: datetime,
    now: datetime | None = None,
  ) -> tuple[bool, str]:
    """
    Hard-validate a schedule timestamp against all rules.

    Checks:
    1. ``dt >= min_allowed_datetime``
    2. ``dt <= max_allowed_datetime``
    3. ``dt.minute`` is a multiple of ``minute_step``

    This method is the **single source of truth** for time validation.
    It is called:
    - In the GUI live validation (``GUIController._validate_time_selection``)
      whenever the user changes the start-time dropdowns.
    - Pre-generation (``GUIController._on_generate_schedule``) before
      building the schedule.
    - Pre-upload (``UploadWorker._execute``) immediately before each
      Playwright submission.

    :param dt: Candidate schedule timestamp.
    :type dt: datetime
    :param now: Reference time (defaults to ``datetime.now()``).
    :type now: datetime | None
    :return: ``(is_valid, reason)`` tuple.
    :rtype: tuple[bool, str]
    """
    if now is None:
      now = datetime.now()

    min_dt = self.min_allowed_datetime(now)
    max_dt = self.max_allowed_datetime(now)

    if dt < min_dt:
      return (
        False,
        f"Too early: must be at least {self._min_offset_minutes} min "
        f"in the future (earliest: {min_dt.strftime('%Y-%m-%d %H:%M')})",
      )

    if dt > max_dt:
      return (
        False,
        f"Too late: must be within {self._max_offset_days} day(s) "
        f"(latest: {max_dt.strftime('%Y-%m-%d %H:%M')})",
      )

    if dt.minute % self._minute_step != 0:
      return (
        False,
        f"Minute must be a multiple of {self._minute_step} "
        f"(got {dt.minute:02d})",
      )

    return (True, "Valid")

  def validate_date_range(
    self,
    start: datetime,
    end: datetime,
    now: datetime | None = None,
  ) -> tuple[bool, str]:
    """
    Validate that a full date range falls within the allowed window.

    Compares **calendar dates** (not exact timestamps) for the
    start/end boundaries, because the GUI date pickers select whole
    days.  Individual upload timestamps are still hard-validated via
    :meth:`validate` before submission.

    :param start: Range start.
    :type start: datetime
    :param end: Range end.
    :type end: datetime
    :param now: Reference time.
    :type now: datetime | None
    :return: ``(is_valid, reason)`` tuple.
    :rtype: tuple[bool, str]
    """
    if now is None:
      now = datetime.now()

    min_dt = self.min_allowed_datetime(now)
    max_dt = self.max_allowed_datetime(now)

    if start > end:
      return (False, "Start date must be before end date")

    if end.date() < min_dt.date():
      return (
        False,
        f"Entire range is in the past or too soon "
        f"(earliest allowed: {min_dt.strftime('%Y-%m-%d')})",
      )

    if start.date() > max_dt.date():
      return (
        False,
        f"Start date exceeds maximum allowed "
        f"({max_dt.strftime('%Y-%m-%d')}). "
        f"Scheduling is limited to {self._max_offset_days} day(s) from now.",
      )

    if end.date() > max_dt.date():
      return (
        False,
        f"End date {end.strftime('%Y-%m-%d')} exceeds the maximum "
        f"allowed date {max_dt.strftime('%Y-%m-%d')}. "
        f"Scheduling is limited to {self._max_offset_days} day(s) from now.",
      )

    return (True, "Valid")

  # ------------------------------------------------------------------
  # Minute step helpers
  # ------------------------------------------------------------------

  def round_minute_up(self, dt: datetime) -> datetime:
    """
    Round a datetime's minute **up** to the next valid step boundary.

    :param dt: Input datetime.
    :type dt: datetime
    :return: Rounded datetime (seconds/microseconds zeroed).
    :rtype: datetime
    """
    m = dt.minute
    remainder = m % self._minute_step
    if remainder == 0:
      return dt.replace(second=0, microsecond=0)
    rounded = m + (self._minute_step - remainder)
    if rounded >= 60:
      return (dt.replace(minute=0, second=0, microsecond=0)
              + timedelta(hours=1))
    return dt.replace(minute=rounded, second=0, microsecond=0)

  def round_minute_nearest(self, dt: datetime) -> datetime:
    """
    Round a datetime's minute to the **nearest** valid step boundary.

    :param dt: Input datetime.
    :type dt: datetime
    :return: Rounded datetime.
    :rtype: datetime
    """
    m = dt.minute
    rounded = round(m / self._minute_step) * self._minute_step
    if rounded >= 60:
      return (dt.replace(minute=0, second=0, microsecond=0)
              + timedelta(hours=1))
    return dt.replace(minute=rounded, second=0, microsecond=0)

  # ------------------------------------------------------------------
  # GUI option generation
  # ------------------------------------------------------------------

  def allowed_hours(self) -> list[str]:
    """
    Full list of zero-padded hour strings (``00`` .. ``23``).

    :return: 24-element list.
    :rtype: list[str]
    """
    return [f"{h:02d}" for h in range(24)]

  def allowed_minutes(self) -> list[str]:
    """
    Full list of zero-padded minute strings at the configured step.

    :return: List like ``['00','05','10', ... ,'55']``.
    :rtype: list[str]
    """
    return [f"{m:02d}" for m in range(0, 60, self._minute_step)]

  def filtered_hours_for_date(
    self,
    selected_date: datetime,
    now: datetime | None = None,
  ) -> list[str]:
    """
    Return hours valid for the given *selected_date*.

    If *selected_date* is today, hours earlier than the minimum
    allowed hour are excluded.  For future dates the full range is
    returned.

    :param selected_date: The date the user picked in the calendar.
    :type selected_date: datetime
    :param now: Reference time.
    :type now: datetime | None
    :return: Filtered list of zero-padded hour strings.
    :rtype: list[str]
    """
    if now is None:
      now = datetime.now()

    min_dt = self.min_allowed_datetime(now)

    if selected_date.date() == now.date():
      min_hour = min_dt.hour
      return [f"{h:02d}" for h in range(min_hour, 24)]

    if selected_date.date() < now.date():
      return []

    return self.allowed_hours()

  def filtered_minutes_for_hour(
    self,
    selected_date: datetime,
    selected_hour: int,
    now: datetime | None = None,
  ) -> list[str]:
    """
    Return minutes valid for the given *selected_date* and *selected_hour*.

    If the date+hour corresponds to the same hour as the minimum
    allowed time, earlier minutes are excluded.

    :param selected_date: The date the user picked.
    :type selected_date: datetime
    :param selected_hour: The hour the user picked (0-23).
    :type selected_hour: int
    :param now: Reference time.
    :type now: datetime | None
    :return: Filtered list of zero-padded minute strings.
    :rtype: list[str]
    """
    if now is None:
      now = datetime.now()

    min_dt = self.min_allowed_datetime(now)
    all_minutes = self.allowed_minutes()

    if selected_date.date() == now.date() and selected_hour == min_dt.hour:
      return [m for m in all_minutes if int(m) >= min_dt.minute]

    if selected_date.date() == now.date() and selected_hour < min_dt.hour:
      return []

    return all_minutes

  # ------------------------------------------------------------------
  # Queue Pre-Validation and Smart Recalculation (Phase 2.5)
  # ------------------------------------------------------------------

  def inspect_queue(
    self,
    tasks: list[Any],
    now: datetime | None = None,
    min_interval_minutes: int = 5,
  ) -> dict[str, Any]:
    """
    Inspect an entire queue of upload tasks before browser launch.

    Detects:
    - Expired times (< now)
    - Insufficient lead time (< min_allowed_datetime)
    - Duplicate times
    - Intervals between consecutive posts (< min_interval_minutes)
    - Times exceeding the 10-day TikTok limit (> max_allowed_datetime)
    - Immediate posts (schedule_time is None)

    :param tasks: List of UploadTask objects.
    :param now: Reference datetime (defaults to datetime.now()).
    :param min_interval_minutes: Minimum minutes required between posts.
    :return: Dictionary containing inspection metrics and status (is_valid: bool).
    """
    if now is None:
      now = datetime.now()

    min_dt = self.min_allowed_datetime(now)
    max_dt = self.max_allowed_datetime(now)

    issues: list[dict[str, Any]] = []
    seen_times: dict[datetime, str] = {}
    last_scheduled_time: datetime | None = None

    for i, t in enumerate(tasks):
      fn = getattr(getattr(t, "file_path", None), "name", f"video_{i+1}")
      sched = getattr(t, "schedule_time", None)

      if sched is None:
        # Immediate publication - always valid in terms of schedule
        continue

      # Check 1: Expired or insufficient lead time (< min_dt)
      if sched < min_dt:
        issues.append({
          "index": i,
          "filename": fn,
          "schedule_time": sched,
          "issue_type": "expired" if sched < now else "insufficient_lead",
          "reason": (
            f"Horário ({sched.strftime('%d/%m %H:%M')}) é anterior à antecedência mínima "
            f"permitida ({min_dt.strftime('%d/%m %H:%M')})"
          ),
        })
        continue

      # Check 2: Beyond max allowed (10 days)
      if sched > max_dt:
        issues.append({
          "index": i,
          "filename": fn,
          "schedule_time": sched,
          "issue_type": "exceeded_max",
          "reason": (
            f"Horário ({sched.strftime('%d/%m %H:%M')}) excede o limite máximo de "
            f"{self._max_offset_days} dias do TikTok (limite: {max_dt.strftime('%d/%m %H:%M')})"
          ),
        })
        continue

      # Check 3: Minute granularity
      if sched.minute % self._minute_step != 0:
        issues.append({
          "index": i,
          "filename": fn,
          "schedule_time": sched,
          "issue_type": "invalid_minute_step",
          "reason": f"Minutos ({sched.minute:02d}) devem ser múltiplos de {self._minute_step}",
        })
        continue

      # Check 4: Duplicate times
      if sched in seen_times:
        issues.append({
          "index": i,
          "filename": fn,
          "schedule_time": sched,
          "issue_type": "duplicate",
          "reason": f"Horário idêntico ao de {seen_times[sched]} ({sched.strftime('%d/%m %H:%M')})",
        })
      else:
        seen_times[sched] = fn

      # Check 5: Interval between consecutive scheduled posts
      if last_scheduled_time is not None:
        gap = (sched - last_scheduled_time).total_seconds() / 60
        if 0 < gap < min_interval_minutes:
          issues.append({
            "index": i,
            "filename": fn,
            "schedule_time": sched,
            "issue_type": "interval_too_short",
            "reason": (
              f"Intervalo de {int(gap)} min em relação ao vídeo anterior é menor que o "
              f"mínimo de {min_interval_minutes} min"
            ),
          })
      last_scheduled_time = sched

    return {
      "is_valid": len(issues) == 0,
      "total_tasks": len(tasks),
      "scheduled_count": sum(1 for t in tasks if getattr(t, "schedule_time", None) is not None),
      "immediate_count": sum(1 for t in tasks if getattr(t, "schedule_time", None) is None),
      "issues": issues,
    }

  def recalculate_schedule_queue(
    self,
    tasks: list[Any],
    interval_minutes: int = 30,
    now: datetime | None = None,
  ) -> list[dict[str, Any]]:
    """
    Generate a new valid, non-colliding, sequential schedule for all scheduled tasks.
    Preserves immediate posts (schedule_time is None) and video order.

    :param tasks: List of tasks.
    :param interval_minutes: Interval in minutes between consecutive scheduled posts.
    :param now: Reference datetime.
    :return: List of dicts with {index, task, filename, old_schedule, new_schedule, changed, reason}.
    """
    if now is None:
      now = datetime.now()

    interval_minutes = max(self._minute_step, interval_minutes)
    current_slot = self.min_allowed_datetime(now)
    max_dt = self.max_allowed_datetime(now)

    recalculated: list[dict[str, Any]] = []

    for i, t in enumerate(tasks):
      fn = getattr(getattr(t, "file_path", None), "name", f"video_{i+1}")
      old_sched = getattr(t, "schedule_time", None)

      if old_sched is None:
        recalculated.append({
          "index": i,
          "task": t,
          "filename": fn,
          "old_schedule": None,
          "new_schedule": None,
          "changed": False,
          "reason": "Publicação imediata",
        })
        continue

      new_slot = current_slot
      if new_slot > max_dt:
        new_slot = max_dt

      reason_parts = []
      if old_sched < self.min_allowed_datetime(now):
        reason_parts.append("Vencido/antecedência insuficiente")
      if old_sched > max_dt:
        reason_parts.append(f"Excedia {self._max_offset_days} dias")

      recalculated.append({
        "index": i,
        "task": t,
        "filename": fn,
        "old_schedule": old_sched,
        "new_schedule": new_slot,
        "changed": old_sched != new_slot,
        "reason": " / ".join(reason_parts) if reason_parts else "Ajuste sequencial de intervalo",
      })

      current_slot = new_slot + timedelta(minutes=interval_minutes)
      current_slot = self.round_minute_up(current_slot)

    return recalculated
