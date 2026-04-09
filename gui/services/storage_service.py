from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.logger_manager import LoggerManager
from core.scheduler import UploadTask
from core.uploader import UploadResult
from utils.datetime_utils import DateTimeUtils


class GuiStorageService:
  """Persist GUI-facing records such as schedules, reports, and folders.

  :param project_root: Project root directory.
  :param storage_dir_name: Relative storage directory name.
  :param logger: Logger used for persistence warnings.
  :return: None
  """

  def __init__(
    self,
    project_root: Path,
    storage_dir_name: str,
    logger: LoggerManager,
  ) -> None:
    """Initialize the storage service.

    :param project_root: Project root directory.
    :param storage_dir_name: Relative storage directory name.
    :param logger: Logger used for persistence warnings.
    :return: None
    """
    self._project_root = project_root
    self._storage_dir = self._project_root / storage_dir_name
    self._schedules_dir = self._storage_dir / "schedules"
    self._publishes_dir = self._storage_dir / "publishes"
    self._logger = logger

  @property
  def storage_dir(self) -> Path:
    """Return the root GUI storage directory.

    :return: Storage directory path.
    """
    return self._storage_dir

  @property
  def schedules_dir(self) -> Path:
    """Return the schedules directory path.

    :return: Schedules directory path.
    """
    return self._schedules_dir

  @property
  def publishes_dir(self) -> Path:
    """Return the publishes directory path.

    :return: Publishes directory path.
    """
    return self._publishes_dir

  def migrate_legacy_scheduled(self) -> None:
    """Migrate the legacy schedule file into per-user JSON files.

    :return: None
    """
    legacy_path = self._storage_dir / "scheduled.json"
    if not legacy_path.exists():
      return

    legacy_data = self._read_json(legacy_path)
    if not isinstance(legacy_data, dict) or not legacy_data:
      return

    self._logger.info("Migrating scheduled.json to per-user files...")
    self._schedules_dir.mkdir(parents=True, exist_ok=True)

    for username, user_data in legacy_data.items():
      if not isinstance(user_data, dict):
        continue
      user_path = self.user_schedule_path(str(username))
      if user_path.exists():
        existing = self._read_json(user_path)
        if isinstance(existing, dict):
          existing_uploads = existing.get("uploads", [])
          new_uploads = user_data.get("uploads", [])
          existing["uploads"] = existing_uploads + new_uploads
          user_data = existing
      try:
        with open(user_path, "w", encoding="utf-8") as file_obj:
          json.dump(user_data, file_obj, indent=2, ensure_ascii=False)
        self._logger.info(f"  Migrated @{username}")
      except OSError as exc:
        self._logger.error(f"  Failed to migrate @{username}: {exc}")

    try:
      legacy_path.rename(legacy_path.with_suffix(".json.migrated"))
      self._logger.success(
        "Migration complete - old file renamed to scheduled.json.migrated"
      )
    except OSError:
      pass

  def read_folder_records(self, target_path_file: str) -> list[dict]:
    """Read saved folder records from disk.

    :param target_path_file: Relative JSON filename for folder records.
    :return: Folder records list.
    """
    target_file = self._storage_dir / target_path_file
    if not target_file.exists():
      return []

    data = self._read_json(target_file)
    if not isinstance(data, dict):
      return []

    records: list[dict] = []
    raw_records = data.get("folders", [])
    if isinstance(raw_records, list) and raw_records:
      for entry in raw_records:
        if not isinstance(entry, dict):
          continue
        folder_path = str(entry.get("path", "")).strip()
        if not folder_path:
          continue
        records.append({
          "path": folder_path,
          "date_added": str(entry.get("date_added", "")),
          "total_videos": entry.get("total_videos"),
        })
      return records

    legacy_folders = data.get("video_folder", [])
    if isinstance(legacy_folders, str):
      legacy_folders = [legacy_folders] if legacy_folders else []
    if not isinstance(legacy_folders, list):
      return []

    created_at = datetime.fromtimestamp(target_file.stat().st_mtime).isoformat()
    for folder in legacy_folders:
      folder_path = str(folder).strip()
      if folder_path:
        records.append({
          "path": folder_path,
          "date_added": created_at,
          "total_videos": None,
        })
    return records

  def write_folder_records(self, target_path_file: str, records: list[dict]) -> None:
    """Persist folder records to disk.

    :param target_path_file: Relative JSON filename for folder records.
    :param records: Folder records to write.
    :return: None
    """
    target_file = self._storage_dir / target_path_file
    payload = {
      "folders": records,
      "video_folder": [record["path"] for record in records],
    }
    self._write_json(target_file, payload, "Failed to save folder path")

  def load_tag_history(
    self,
    tag_history_file: str,
    extract_tags: Callable[[str], list[str]],
  ) -> list[str]:
    """Load tag suggestions from disk or scheduled captions.

    :param tag_history_file: Relative JSON filename for tag history.
    :param extract_tags: Callable used to parse tags from captions.
    :return: Ordered tag list without ``#`` prefixes.
    """
    history_path = self._storage_dir / tag_history_file
    if history_path.exists():
      data = self._read_json(history_path)
      if isinstance(data, list):
        return [
          str(tag).lstrip("#").lower()
          for tag in data
          if str(tag).strip()
        ]

    tags: list[str] = []
    if self._schedules_dir.exists():
      for schedule_file in self._schedules_dir.glob("*.json"):
        data = self._read_json(schedule_file)
        if not isinstance(data, dict):
          continue
        for upload in data.get("uploads", []):
          caption = str(upload.get("caption", ""))
          for tag in extract_tags(caption):
            if tag not in tags:
              tags.append(tag)
    return tags

  def save_tag_history(self, tag_history_file: str, tags: list[str]) -> None:
    """Persist tag history to disk.

    :param tag_history_file: Relative JSON filename for tag history.
    :param tags: Ordered tags list.
    :return: None
    """
    history_path = self._storage_dir / tag_history_file
    self._write_json(history_path, tags, "Failed to save tag history")

  def user_schedule_path(self, username: str) -> Path:
    """Build the path for a user's schedule file.

    :param username: Account username.
    :return: Schedule file path.
    """
    return self._schedules_dir / f"@{username}.json"

  def load_scheduled(self, username: str) -> dict:
    """Load one user's scheduled uploads.

    :param username: Account username.
    :return: Schedule record dictionary.
    """
    path = self.user_schedule_path(username)
    data = self._read_json(path)
    if isinstance(data, dict):
      return data
    return {"uploads": []}

  def save_scheduled(self, username: str, data: dict) -> None:
    """Save one user's scheduled uploads atomically.

    :param username: Account username.
    :param data: Schedule record dictionary.
    :return: None
    """
    path = self.user_schedule_path(username)
    self._write_json_atomic(path, data, "Failed to save schedule")

  def user_publish_path(self, username: str) -> Path:
    """Build the path for a user's publish archive file.

    :param username: Account username.
    :return: Publish file path.
    """
    return self._publishes_dir / f"@{username}.json"

  def load_published(self, username: str) -> dict:
    """Load one user's published uploads.

    :param username: Account username.
    :return: Publish record dictionary.
    """
    path = self.user_publish_path(username)
    data = self._read_json(path)
    if isinstance(data, dict):
      return data
    return {"published": []}

  def save_published(self, username: str, data: dict) -> None:
    """Save one user's published uploads atomically.

    :param username: Account username.
    :param data: Publish record dictionary.
    :return: None
    """
    path = self.user_publish_path(username)
    self._write_json_atomic(path, data, "Failed to save publishes")

  def rename_account_artifacts(
    self,
    original_username: str,
    new_username: str,
  ) -> None:
    """Rename per-user schedule and publish files after account edits.

    :param original_username: Previous username.
    :param new_username: Updated username.
    :return: None
    """
    if original_username == new_username:
      return

    old_schedule = self.user_schedule_path(original_username)
    new_schedule = self.user_schedule_path(new_username)
    old_publish = self.user_publish_path(original_username)
    new_publish = self.user_publish_path(new_username)

    try:
      if old_schedule.exists() and not new_schedule.exists():
        old_schedule.rename(new_schedule)
      if old_publish.exists() and not new_publish.exists():
        old_publish.rename(new_publish)
    except OSError as exc:
      self._logger.error(f"Failed to rename account artifacts: {exc}")

  def migrate_to_published(
    self,
    username: str,
    entries: list[dict],
    normalize_video_id: Callable[[Path], str],
  ) -> None:
    """Move past-due scheduled entries into the publish archive.

    :param username: Account username.
    :param entries: Entries that should be moved.
    :param normalize_video_id: Callable used to derive a video id.
    :return: None
    """
    published_data = self.load_published(username)
    existing_entries = set(published_data.get("published", []))

    for entry in entries:
      filename = str(entry.get("file", ""))
      schedule_time = str(entry.get("schedule_time", ""))
      video_id = normalize_video_id(Path(filename))
      existing_entries.add(f"{video_id}|{schedule_time}")

    published_data["published"] = sorted(existing_entries)
    self.save_published(username, published_data)

    scheduled_data = self.load_scheduled(username)
    migrated_files = {entry.get("file") for entry in entries}
    scheduled_data["uploads"] = [
      upload for upload in scheduled_data.get("uploads", [])
      if upload.get("file") not in migrated_files
    ]
    self.save_scheduled(username, scheduled_data)
    self._logger.info(
      f"Migrated {len(entries)} published entry/entries for @{username}"
    )

  def get_user_uploads(self, data: dict) -> list[dict]:
    """Extract the upload list from a schedule record.

    :param data: Schedule record dictionary.
    :return: Upload records.
    """
    return data.get("uploads", [])

  def append_upload_record(
    self,
    data: dict,
    task: UploadTask,
    result: UploadResult,
  ) -> None:
    """Append an upload result to a schedule record.

    :param data: Schedule record dictionary.
    :param task: Upload task.
    :param result: Upload result.
    :return: None
    """
    if "uploads" not in data:
      data["uploads"] = []

    scheduled_at = task.schedule_time or result.timestamp
    record = {
      "file": task.file_path.name,
      "caption": task.caption,
      "schedule_time": (
        DateTimeUtils.format_iso(task.schedule_time)
        if task.schedule_time else None
      ),
      "status": "success" if result.success else "failed",
      "timestamp": int(scheduled_at.timestamp()),
      "video_id": None,
      "cm": result.cm,
      "qc": result.qc,
    }
    data["uploads"].append(record)

  def last_used_timestamp(self, username: str) -> float | None:
    """Return the latest known activity timestamp for an account.

    :param username: Account username.
    :return: Latest timestamp or ``None``.
    """
    latest = 0.0

    for upload in self.load_scheduled(username).get("uploads", []):
      raw_timestamp = upload.get("timestamp")
      if isinstance(raw_timestamp, (int, float)):
        latest = max(latest, float(raw_timestamp))
        continue
      schedule_time = upload.get("schedule_time")
      if isinstance(schedule_time, str) and schedule_time:
        try:
          latest = max(latest, datetime.fromisoformat(schedule_time).timestamp())
        except ValueError:
          pass

    for entry in self.load_published(username).get("published", []):
      if "|" not in entry:
        continue
      _video_id, raw_date = entry.split("|", 1)
      if not raw_date:
        continue
      try:
        latest = max(latest, datetime.fromisoformat(raw_date).timestamp())
      except ValueError:
        continue

    return latest or None

  def _read_json(self, path: Path) -> object | None:
    """Read arbitrary JSON content from disk.

    :param path: Target JSON path.
    :return: Parsed JSON data or ``None``.
    """
    if not path.exists():
      return None
    try:
      with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)
    except (json.JSONDecodeError, OSError):
      return None

  def _write_json(self, path: Path, data: object, error_prefix: str) -> None:
    """Write JSON content to disk.

    :param path: Target JSON path.
    :param data: JSON-serializable data.
    :param error_prefix: Error prefix for logging.
    :return: None
    """
    try:
      path.parent.mkdir(parents=True, exist_ok=True)
      with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(data, file_obj, indent=2, ensure_ascii=False)
    except OSError as exc:
      self._logger.error(f"{error_prefix}: {exc}")

  def _write_json_atomic(self, path: Path, data: dict, error_prefix: str) -> None:
    """Write dictionary JSON content atomically.

    :param path: Target JSON path.
    :param data: Dictionary payload.
    :param error_prefix: Error prefix for logging.
    :return: None
    """
    temp_path = path.with_suffix(".tmp")
    try:
      path.parent.mkdir(parents=True, exist_ok=True)
      with open(temp_path, "w", encoding="utf-8") as file_obj:
        json.dump(data, file_obj, indent=2, ensure_ascii=False)
      temp_path.replace(path)
    except OSError as exc:
      self._logger.error(f"{error_prefix}: {exc}")
