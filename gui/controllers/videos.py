from __future__ import annotations

import re
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView, QTableWidgetItem

from gui.tables.video_table import build_status_badge
from utils.datetime_utils import DateTimeUtils
from utils.file_scanner import FileScanner, VideoFile
from utils.validators import Validators


class VideoQueueControllerMixin:
  """Handle folder scans, tag suggestions, and video queue tables."""

  def _update_caption_preview(self) -> None:
    """Update the caption preview label.

    :return: None
    """
    if self._videos:
      video_id = self._normalize_video_id(self._videos[0].path)
    else:
      video_id = "<videoid>"

    use_prefix = (
      hasattr(self._window, "prefix_caption_check")
      and self._window.prefix_caption_check.isChecked()
    )
    parts: list[str] = []
    if use_prefix:
      parts.append(f"Cre: {video_id}")
    caption_body = self._window.caption_input.toPlainText().strip()
    if caption_body:
      parts.append(caption_body)

    preview_text = " | ".join(parts) if parts else "(empty)"
    self._window.caption_preview.setText(f"Preview: {preview_text}")

  def _extract_tags(self, text: str) -> list[str]:
    """Extract normalized hashtags from free-form text.

    :param text: Source text.
    :return: Ordered tags without ``#``.
    """
    tags: list[str] = []
    for match in re.findall(r"#([A-Za-z0-9_]+)", text):
      normalized = match.lower()
      if normalized not in tags:
        tags.append(normalized)
    return tags

  def _register_tags(self, text: str) -> None:
    """Add tags from a caption to the suggestion history.

    :param text: Caption text.
    :return: None
    """
    tags = self._extract_tags(text)
    if not tags:
      return

    for tag in reversed(tags):
      if tag in self._tag_history:
        self._tag_history.remove(tag)
      self._tag_history.insert(0, tag)
    self._tag_history = self._tag_history[:200]
    self._storage_service.save_tag_history(self.TAG_HISTORY_FILE, self._tag_history)

  def _get_tag_suggestions(self, prefix: str) -> list[str]:
    """Return hashtag suggestions ordered by similarity.

    :param prefix: User-entered tag prefix without ``#``.
    :return: Ordered suggestion list.
    """
    normalized_prefix = prefix.lower().lstrip("#")
    if not normalized_prefix:
      return self._tag_history[:8]

    scored: list[tuple[float, str]] = []
    for tag in self._tag_history:
      starts_with = tag.startswith(normalized_prefix)
      contains = normalized_prefix in tag
      similarity = SequenceMatcher(None, normalized_prefix, tag).ratio()
      if not starts_with and not contains and similarity < 0.35:
        continue
      score = similarity
      if contains:
        score += 0.3
      if starts_with:
        score += 0.6
      scored.append((score, tag))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [tag for _score, tag in scored[:8]]

  def _on_limit_changed(self, value: int) -> None:
    """Refresh selected counts for the active selection limit.

    :param value: New limit value.
    :return: None
    """
    _value = value
    if self._videos:
      self._refresh_video_table()

  def _on_scan_clicked(self) -> None:
    """Scan the selected folder for video files.

    :return: None
    """
    folder = self._window.folder_dropdown.currentText()
    if not folder:
      self._logger.warning("No folder selected")
      return

    path = Validators.sanitize_path(folder)
    if not Validators.validate_directory(path):
      self._logger.error(f"Invalid directory: {path}")
      return

    self._videos = self._scanner.scan(path)
    self._update_folder_record_total(folder, len(self._videos))

    self._scheduled_basenames = set()
    self._failed_basenames = set()
    self._unknown_basenames = set()
    self._published_video_ids = set()
    self._published_entries = {}

    username = self._window.account_dropdown.currentText()
    existing: list[dict] = []
    if username:
      scheduled_data = self._storage_service.load_scheduled(username)
      existing = self._storage_service.get_user_uploads(scheduled_data)

      latest_status_by_file: dict[str, str] = {}
      for upload in existing:
        fname = Path(str(upload.get("file", ""))).name
        st = str(upload.get("status", ""))
        if fname and st:
          latest_status_by_file[fname] = st

      self._scheduled_basenames = {
        fname
        for fname, st in latest_status_by_file.items()
        if st in ("scheduled", "success", "unknown")
      }
      self._unknown_basenames = {
        fname
        for fname, st in latest_status_by_file.items()
        if st == "unknown"
      }
      self._failed_basenames = {
        fname
        for fname, st in latest_status_by_file.items()
        if st == "failed"
      }

      # Past-due scheduled entries are NOT automatically moved to published,
      # because elapsed local clock time does not prove publication on TikTok.
      # They remain in schedules/@username.json and are displayed as
      # 'Elapsed (Unverified)' while staying blocked against automatic re-upload.

      published_data = self._storage_service.load_published(username)
      for entry in published_data.get("published", []):
        if "|" in entry:
          video_id, date_str = entry.split("|", 1)
        else:
          video_id, date_str = entry, ""
        if video_id:
          self._published_video_ids.add(video_id)
          self._published_entries[video_id] = date_str

    total_all = len(self._videos)
    total_available = sum(
      1
      for video in self._videos
      if not self._is_video_unavailable(video.filename)
    )

    self._window.video_total_label.setText(f"Total: {total_available}")

    limit_max = max(1, total_available)
    self._window.limit_spin.setMaximum(limit_max)
    self._window.limit_spin.setValue(limit_max)

    self._populate_video_table(existing, username)
    self._update_caption_preview()
    if hasattr(self, "_refresh_wizard_videos_page"):
      self._refresh_wizard_videos_page()

  def _is_video_unavailable(self, filename: str) -> bool:
    """Return whether a video is already scheduled, unknown, or published.

    :param filename: Video filename.
    :return: ``True`` when unavailable.
    """
    if filename in self._scheduled_basenames or filename in self._unknown_basenames:
      return True
    stem = Path(filename).stem
    normalized_id = self._normalize_video_id(Path(filename))
    for video_id in self._published_video_ids:
      if video_id == filename or video_id == stem or (
        "_" not in stem and video_id == normalized_id
      ):
        return True
    return False

  def lookup_scheduled(self, filename: str, uploads: list[dict]) -> dict | None:
    """Look up the latest scheduled upload entry for an exact filename.

    :param filename: Video filename.
    :param uploads: Upload records.
    :return: Schedule metadata or ``None``.
    """
    stem = Path(filename).stem
    for upload in reversed(uploads):
      upload_file = Path(str(upload.get("file", ""))).name
      upload_video_id = str(upload.get("video_id") or "")
      matches = (
        upload_file == filename
        or (upload_video_id and upload_video_id in (filename, stem))
      )
      if not matches:
        continue

      schedule_time = str(upload.get("schedule_time") or "")
      if schedule_time:
        try:
          schedule_dt = datetime.fromisoformat(schedule_time)
          return {
            "date": self._format_iso_datetime(schedule_time),
            "timestamp": schedule_dt.timestamp(),
          }
        except ValueError:
          return {
            "date": schedule_time,
            "timestamp": 0.0,
          }

      timestamp = upload.get("timestamp")
      if timestamp:
        return {
          "date": datetime.fromtimestamp(timestamp).strftime("%d %b %Y %H:%M"),
          "timestamp": float(timestamp),
        }
    return None

  def _lookup_published(self, filename: str) -> tuple[bool, str]:
    """Look up published metadata for an exact filename or stem.

    :param filename: Video filename.
    :return: Tuple of match flag and formatted published date.
    """
    stem = Path(filename).stem
    normalized_id = self._normalize_video_id(Path(filename))
    for video_id, raw_date in self._published_entries.items():
      if video_id == filename or video_id == stem or (
        "_" not in stem and video_id == normalized_id
      ):
        return True, self._format_iso_datetime(raw_date) if raw_date else "-"
    return False, "-"

  def _populate_video_table(
    self,
    data_uploads: list[dict] | None = None,
    username: str = "",
  ) -> None:
    """Cache upload data and rebuild queue tables.

    :param data_uploads: Upload records to display.
    :param username: Active username.
    :return: None
    """
    self._cached_data_uploads = data_uploads or []
    self._cached_username = username
    self._refresh_video_table()

  def _refresh_video_table(self) -> None:
    """Rebuild the table from cached data applying filters and sort.

    :return: None
    """
    data_uploads = self._cached_data_uploads
    limit = self._window.limit_spin.value()
    filter_state = {
      "Pending": self._window.filter_pending_check.isChecked(),
      "Scheduled": self._window.filter_scheduled_check.isChecked(),
      "Published": self._window.filter_published_check.isChecked(),
      "Failed": self._window.filter_failed_check.isChecked(),
    }
    status_totals = {name: 0 for name in filter_state}

    now_ts = datetime.now().timestamp()
    rows: list[tuple[VideoFile, str, str, str, float, int]] = []
    for video in self._videos:
      is_unknown = video.filename in getattr(self, "_unknown_basenames", set())
      is_scheduled = video.filename in self._scheduled_basenames and not is_unknown
      is_failed = video.filename in self._failed_basenames
      is_published, published_text = self._lookup_published(video.filename)
      scheduled = self.lookup_scheduled(video.filename, data_uploads)
      schedule_text = scheduled["date"] if scheduled else "-"

      if is_unknown:
        status = "Unknown"
        sort_ts = scheduled.get("timestamp", 0) if scheduled else 0
        filter_bucket = "Failed"
      elif is_scheduled:
        sort_ts = scheduled.get("timestamp", 0) if scheduled else 0
        if sort_ts and sort_ts < now_ts:
          status = "Elapsed (Unverified)"
        else:
          status = "Scheduled"
        filter_bucket = "Scheduled"
      elif is_published:
        status = "Published"
        sort_ts = 0.0
        filter_bucket = "Published"
      elif is_failed:
        status = "Failed"
        sort_ts = 0.0
        filter_bucket = "Failed"
      else:
        status = "Pending"
        sort_ts = 0.0
        filter_bucket = "Pending"

      status_totals[filter_bucket] += 1
      if filter_state[filter_bucket]:
        rows.append((
          video,
          status,
          schedule_text,
          published_text,
          sort_ts,
          video.size_bytes,
        ))

    self._window.filter_pending_check.setText(
      f"[{status_totals['Pending']}] Pending"
    )
    self._window.filter_scheduled_check.setText(
      f"[{status_totals['Scheduled']}] Scheduled"
    )
    self._window.filter_published_check.setText(
      f"[{status_totals['Published']}] Published"
    )
    self._window.filter_failed_check.setText(
      f"[{status_totals['Failed']}] Failed"
    )

    if self._sort_column is not None:
      if self._sort_column == 1:
        rows.sort(
          key=lambda row: row[0].filename.lower(),
          reverse=not self._sort_ascending,
        )
      elif self._sort_column == 2:
        rows.sort(key=lambda row: row[5], reverse=not self._sort_ascending)
      elif self._sort_column == 3:
        rows.sort(key=lambda row: row[4], reverse=not self._sort_ascending)

    selected_count = self._populate_video_table_widget(
      self._window.video_table,
      rows,
      limit,
      allow_selection=True,
      track_rows=True,
    )
    for mirror_table in self._iter_secondary_video_tables():
      self._populate_video_table_widget(
        mirror_table,
        rows,
        limit,
        allow_selection=False,
        track_rows=False,
      )

    self._window.video_selected_label.setText(f"Selected: {selected_count}")
    self._window.video_total_label.setText(f"Total: {len(rows)}")
    if hasattr(self, "_update_execution_metrics"):
      self._update_execution_metrics()

  def _populate_video_table_widget(
    self,
    table,
    rows: list[tuple[VideoFile, str, str, str, float, int]],
    limit: int,
    allow_selection: bool,
    track_rows: bool,
  ) -> int:
    """Populate a video table widget from row data.

    :param table: Target table widget.
    :param rows: Row data.
    :param limit: Selection limit.
    :param allow_selection: Whether checkboxes should be interactive.
    :param track_rows: Whether to refresh the row-to-video map.
    :return: Number of selected pending rows.
    """
    if table is None:
      return 0
    table.setRowCount(len(rows))
    if track_rows:
      self._row_video_map.clear()

    pending_index = 0
    selected_count = 0
    for row_index, (video, status, schedule_text, published_text, _sort_ts, _size_bytes) in enumerate(rows):
      if track_rows:
        self._row_video_map[row_index] = video

      row_item = QTableWidgetItem(str(row_index + 1))
      row_item.setFlags(row_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
      row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 0, row_item)

      filename_item = QTableWidgetItem(video.filename)
      filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
      filename_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 1, filename_item)

      size_item = QTableWidgetItem(video.size_human)
      size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
      size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 2, size_item)

      schedule_item = QTableWidgetItem(schedule_text)
      schedule_item.setFlags(schedule_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
      schedule_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 3, schedule_item)

      published_item = QTableWidgetItem(published_text)
      published_item.setFlags(published_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
      published_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 4, published_item)

      status_item = QTableWidgetItem(status)
      status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
      status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 5, status_item)
      table.setCellWidget(row_index, 5, build_status_badge(status))

      if allow_selection and status in ("Pending", "Failed") and pending_index < limit:
        selected_count += 1
      if status in ("Pending", "Failed"):
        pending_index += 1

    table.resizeColumnsToContents()
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    table.setColumnWidth(5, max(table.columnWidth(5), 156))
    table.horizontalHeader().setStretchLastSection(False)
    table.resizeRowsToContents()
    for row_index in range(table.rowCount()):
      table.setRowHeight(row_index, max(table.rowHeight(row_index), 50))

    return selected_count

  def _on_filter_changed(self) -> None:
    """Re-populate tables when filter checkboxes change.

    :return: None
    """
    if self._videos:
      self._refresh_video_table()

  def _on_header_clicked(self, logical_index: int) -> None:
    """Handle column header clicks for sorting.

    :param logical_index: Clicked column index.
    :return: None
    """
    if logical_index not in (1, 2, 3):
      return
    if self._sort_column == logical_index:
      self._sort_ascending = not self._sort_ascending
    else:
      self._sort_column = logical_index
      self._sort_ascending = True
    if self._videos:
      self._refresh_video_table()

  def _get_selected_videos(self) -> list[VideoFile]:
    """Return eligible videos (Pending, plus confirmed Failed when visible) in the main queue table.

    Videos with status Scheduled, Elapsed (Unverified), Published, or Unknown
    are strictly excluded to prevent duplicate or unverified re-uploads.

    :return: Selected video files.
    """
    selected: list[VideoFile] = []
    limit = self._window.limit_spin.value()
    table = self._window.video_table
    pending_index = 0
    for row in range(table.rowCount()):
      status_item = table.item(row, 5)
      if status_item and status_item.text() in (
        "Scheduled",
        "Elapsed (Unverified)",
        "Published",
        "Unknown",
      ):
        continue
      if pending_index >= limit:
        break
      video = self._row_video_map.get(row)
      if video is not None:
        selected.append(video)
        pending_index += 1
    return selected

  def _update_table_schedule(self) -> None:
    """Write generated schedule times into both video tables.

    :return: None
    """
    for table in (self._window.video_table, *self._iter_secondary_video_tables()):
      for task in self._tasks:
        for row in range(table.rowCount()):
          filename_item = table.item(row, 1)
          if filename_item and filename_item.text() == task.file_path.name:
            time_text = ""
            if task.schedule_time:
              time_text = DateTimeUtils.format_for_display(task.schedule_time)
            time_item = QTableWidgetItem(time_text)
            time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 3, time_item)
            break

  def _iter_secondary_video_tables(self) -> list:
    """Return optional secondary video tables that mirror the queue.

    :return: Secondary table widgets.
    """
    table = getattr(self._window, "video_library_table", None)
    if table is None:
      return []
    return [table]
