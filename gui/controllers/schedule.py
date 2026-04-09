from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.scheduler import ScheduleConfig


class ScheduleControllerMixin:
  """Handle date/time validation and schedule generation."""

  def _validate_date_range(self) -> None:
    """Validate the current date range against scheduling rules.

    :return: None
    """
    start_qdate = self._window.start_date.date()
    end_qdate = self._window.end_date.date()
    start_dt = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day())
    end_dt = datetime(
      end_qdate.year(),
      end_qdate.month(),
      end_qdate.day(),
      23,
      59,
    )

    valid, reason = self._rules.validate_date_range(start_dt, end_dt)
    if valid:
      self._window.clear_schedule_warning()
      self._window.set_actions_enabled(True)
      self._validate_time_selection()
    else:
      self._window.show_schedule_warning(reason)
      self._window.set_actions_enabled(False)

  def _update_time_options(self) -> None:
    """Refresh available start-hour options for the selected date.

    :return: None
    """
    qdate = self._window.start_date.date()
    now = datetime.now()
    current_hour = self._window.time_start_hour.currentText()

    if qdate.toPyDate() == now.date():
      hours = [f"{hour:02d}" for hour in range(now.hour, 24)]
    elif qdate.toPyDate() < now.date():
      hours = []
    else:
      hours = [f"{hour:02d}" for hour in range(24)]

    self._window.time_start_hour.blockSignals(True)
    self._window.time_start_hour.clear()
    self._window.time_start_hour.addItems(hours)
    self._window.time_start_hour.blockSignals(False)

    index = self._window.time_start_hour.findText(current_hour)
    if index >= 0:
      self._window.time_start_hour.setCurrentIndex(index)
    elif self._window.time_start_hour.count() > 0:
      self._window.time_start_hour.setCurrentIndex(0)

    self._update_start_minutes()

  def _update_start_minutes(self) -> None:
    """Refresh available start-minute options for the selected hour.

    :return: None
    """
    qdate = self._window.start_date.date()
    now = datetime.now()
    hour_text = self._window.time_start_hour.currentText()
    if not hour_text:
      return

    selected_hour = int(hour_text)
    current_minute = self._window.time_start_minute.currentText()
    step = 5
    all_minutes = [f"{minute:02d}" for minute in range(0, 60, step)]

    if qdate.toPyDate() == now.date() and selected_hour == now.hour:
      rounded_minute = now.minute
      remainder = rounded_minute % step
      if remainder != 0:
        rounded_minute += step - remainder
      if rounded_minute >= 60:
        minutes = []
      else:
        minutes = [f"{minute:02d}" for minute in range(rounded_minute, 60, step)]
    else:
      minutes = all_minutes

    self._window.time_start_minute.blockSignals(True)
    self._window.time_start_minute.clear()
    self._window.time_start_minute.addItems(minutes)
    self._window.time_start_minute.blockSignals(False)

    index = self._window.time_start_minute.findText(current_minute)
    if index >= 0:
      self._window.time_start_minute.setCurrentIndex(index)
    elif self._window.time_start_minute.count() > 0:
      self._window.time_start_minute.setCurrentIndex(0)

    self._validate_time_selection()

  def _initialize_time_defaults(self) -> None:
    """Initialize start time to now plus 15 minutes, rounded to 5.

    :return: None
    """
    now = datetime.now()
    step = 5
    total_minutes = now.hour * 60 + now.minute + 15
    remainder = total_minutes % step
    if remainder != 0:
      total_minutes += step - remainder
    default_hour = (total_minutes // 60) % 24
    default_minute = total_minutes % 60

    self._update_time_options()

    self._window.time_start_hour.blockSignals(True)
    hour_text = f"{default_hour:02d}"
    index = self._window.time_start_hour.findText(hour_text)
    if index >= 0:
      self._window.time_start_hour.setCurrentIndex(index)
    elif self._window.time_start_hour.count() > 0:
      self._window.time_start_hour.setCurrentIndex(0)
    self._window.time_start_hour.blockSignals(False)

    self._update_start_minutes()

    self._window.time_start_minute.blockSignals(True)
    minute_text = f"{default_minute:02d}"
    index = self._window.time_start_minute.findText(minute_text)
    if index >= 0:
      self._window.time_start_minute.setCurrentIndex(index)
    elif self._window.time_start_minute.count() > 0:
      self._window.time_start_minute.setCurrentIndex(0)
    self._window.time_start_minute.blockSignals(False)

  def _validate_time_selection(self) -> None:
    """Ensure the selected start time is allowed for the chosen date.

    :return: None
    """
    qdate = self._window.start_date.date()
    now = datetime.now()
    if qdate.toPyDate() != now.date():
      self._window.clear_time_warning()
      return

    hour_text = self._window.time_start_hour.currentText()
    minute_text = self._window.time_start_minute.currentText()
    if not hour_text or not minute_text:
      self._window.clear_time_warning()
      return

    selected_dt = datetime(
      qdate.year(),
      qdate.month(),
      qdate.day(),
      int(hour_text),
      int(minute_text),
    )
    valid, _reason = self._rules.validate(selected_dt, now)
    if not valid:
      min_dt = self._rules.min_allowed_datetime(now)
      self._window.show_time_warning(
        f"Start time must be at least 15 min from now (earliest: {min_dt.strftime('%H:%M')})"
      )
      self._window.set_actions_enabled(False)
      return

    self._window.clear_time_warning()
    start_dt = datetime(qdate.year(), qdate.month(), qdate.day())
    end_qdate = self._window.end_date.date()
    end_dt = datetime(
      end_qdate.year(),
      end_qdate.month(),
      end_qdate.day(),
      23,
      59,
    )
    date_valid, _ = self._rules.validate_date_range(start_dt, end_dt, now)
    if date_valid:
      self._window.set_actions_enabled(True)

  def _on_generate_schedule(self) -> None:
    """Generate schedule slots and assign them to selected videos.

    :return: None
    """
    self._window.schedule_result_label.clear()
    self._window.schedule_result_label.hide()
    self._validate_date_range()
    self._validate_time_selection()
    if self._window.schedule_warning.isVisible():
      self._logger.warning("Cannot generate schedule - date range invalid")
      return
    if self._window.time_warning.isVisible():
      self._logger.warning("Cannot generate schedule - start time invalid")
      return
    if not self._videos:
      self._logger.warning("No videos to schedule. Scan a folder first.")
      return

    start_qdate = self._window.start_date.date()
    end_qdate = self._window.end_date.date()
    start_hour = int(self._window.time_start_hour.currentText() or "9")
    start_minute = int(self._window.time_start_minute.currentText() or "0")
    end_hour = int(self._window.time_end_hour.currentText() or "23")
    end_minute = int(self._window.time_end_minute.currentText() or "55")

    start_dt = datetime(
      start_qdate.year(),
      start_qdate.month(),
      start_qdate.day(),
      start_hour,
      start_minute,
    )
    end_dt = datetime(
      end_qdate.year(),
      end_qdate.month(),
      end_qdate.day(),
      end_hour,
      end_minute,
    )

    config = ScheduleConfig(
      start_date=start_dt,
      end_date=end_dt,
      interval_minutes=self._window.interval_spin.value(),
      time_window_start=(start_hour, start_minute),
      time_window_end=(end_hour, end_minute),
    )

    try:
      slots = self._scheduler.generate_slots(config)
    except Exception as exc:
      self._logger.error(f"Schedule generation failed: {exc}")
      return

    selected_videos = self._get_selected_videos()
    if not selected_videos:
      self._logger.warning("No videos selected")
      return

    limit = self._window.limit_spin.value()
    selected_videos = selected_videos[:limit]
    slots = slots[:limit]
    video_paths = [video.path for video in selected_videos]

    caption_body = self._window.caption_input.toPlainText().strip()
    self._register_tags(caption_body)
    captions = [
      self._build_caption(video.path, caption_body)
      for video in selected_videos
    ]

    self._tasks = self._scheduler.assign_videos(video_paths, slots, captions)
    self._update_table_schedule()
    self._window.start_btn.setEnabled(len(self._tasks) > 0)
    self._logger.info(f"Schedule generated: {len(self._tasks)} upload(s)")
    self._window.schedule_result_label.setText(
      f"Generated {len(self._tasks)} items. Review the queue table above the terminal."
    )
    self._window.schedule_result_label.show()

  @staticmethod
  def _normalize_video_id(file_path: Path) -> str:
    """Extract a clean video id from a filename.

    :param file_path: Path to the video file.
    :return: Normalized video id.
    """
    stem = file_path.stem
    if "_" in stem:
      return stem.split("_")[0]
    return stem

  @staticmethod
  def _build_caption(file_path: Path, caption_body: str) -> str:
    """Build the final caption for a video.

    :param file_path: Path to the video file.
    :param caption_body: Combined caption and hashtag text.
    :return: Assembled caption string.
    """
    video_id = ScheduleControllerMixin._normalize_video_id(file_path)
    parts = [f"Cre: {video_id}"]
    if caption_body:
      parts.append(caption_body)
    return "\n".join(parts)
