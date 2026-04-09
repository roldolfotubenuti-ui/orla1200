from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer

from core.config_manager import ConfigManager
from core.cookie_manager import CookieManager
from core.logger_manager import LoggerManager
from core.schedule_rule_engine import ScheduleRuleEngine
from core.scheduler import Scheduler, UploadTask
from gui.controllers import (
  AccountsControllerMixin,
  ControllerSignalsMixin,
  ControllerUiMixin,
  FolderControllerMixin,
  ScheduleControllerMixin,
  UploadExecutionControllerMixin,
  UploadWorker,
  VideoQueueControllerMixin,
)
from gui.main_window import MainWindow
from gui.services import GuiStorageService
from utils.file_scanner import FileScanner, VideoFile


class GUIController(
  ControllerSignalsMixin,
  ControllerUiMixin,
  AccountsControllerMixin,
  FolderControllerMixin,
  VideoQueueControllerMixin,
  ScheduleControllerMixin,
  UploadExecutionControllerMixin,
):
  """Coordinate GUI workflows without keeping all logic in one file.

  :param window: Main application window.
  :param config: Application configuration.
  :param project_root: Project root directory.
  :return: None
  """

  TARGET_PATH_FILE = "target-path.json"
  TAG_HISTORY_FILE = "tag-history.json"
  VALIDATION_TIMER_INTERVAL = 60_000

  def __init__(
    self,
    window: MainWindow,
    config: ConfigManager,
    project_root: Path,
  ) -> None:
    """Initialize controller state and wire the GUI to core services.

    :param window: Main application window.
    :param config: Application configuration.
    :param project_root: Project root directory.
    :return: None
    """
    self._window = window
    self._config = config
    self._root = project_root
    self._cookies_dir = self._root / config.cookies_dir

    self._logger = LoggerManager(
      name="TikTokGUI",
      level=config.effective_log_level,
    )
    self._storage_service = GuiStorageService(
      project_root=self._root,
      storage_dir_name=config.storage_dir,
      logger=self._logger,
    )
    self._storage_dir = self._storage_service.storage_dir
    self._schedules_dir = self._storage_service.schedules_dir
    self._publishes_dir = self._storage_service.publishes_dir

    self._cookie_manager = CookieManager(self._cookies_dir, self._logger)
    self._scanner = FileScanner(self._logger)
    self._rules = ScheduleRuleEngine(config)
    self._scheduler = Scheduler(self._rules, self._logger)

    self._videos: list[VideoFile] = []
    self._tasks: list[UploadTask] = []
    self._worker: UploadWorker | None = None

    self._cached_data_uploads: list[dict] = []
    self._cached_username = ""
    self._sort_column: int | None = None
    self._sort_ascending = True
    self._row_video_map: dict[int, VideoFile] = {}

    self._scheduled_basenames: set[str] = set()
    self._failed_basenames: set[str] = set()
    self._published_video_ids: set[str] = set()
    self._published_entries: dict[str, str] = {}

    self._logger.set_callback(self._on_log_message)
    for warning in config.warnings:
      self._logger.warning(f"[config] {warning}")

    self._storage_service.migrate_legacy_scheduled()
    self._tag_history = self._storage_service.load_tag_history(
      self.TAG_HISTORY_FILE,
      self._extract_tags,
    )

    self._window.headless_check.setChecked(config.headless_default)
    self._window.caption_input.set_suggestion_provider(self._get_tag_suggestions)

    self._connect_signals()
    self._load_accounts()
    self._load_saved_folder()
    self._initialize_time_defaults()
    self._validate_date_range()
    self._validate_time_selection()

    self._validation_timer = QTimer()
    self._validation_timer.timeout.connect(self._validate_date_range)
    self._validation_timer.timeout.connect(self._update_time_options)
    self._validation_timer.timeout.connect(self._validate_time_selection)
    self._validation_timer.start(self.VALIDATION_TIMER_INTERVAL)
