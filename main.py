from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from gui.controller import GUIController
from gui.dialogs.first_run_dialog import FirstRunDialog
from gui.main_window import MainWindow
from gui.theme import ThemeManager
from utils.app_paths import (
    configure_playwright_environment,
    get_app_bundle_dir,
    get_logs_dir,
    get_storage_dir,
    get_user_data_dir,
    is_frozen,
    resolve_config_path,
)


class Application:
  """
  Main entry point for the TKS Engine 2.0 standalone application.

  Resolves portable user data in %APPDATA%/TKS_Engine, configures bundled Playwright,
  displays first-run setup wizard on initial launch, and runs the standalone desktop interface.
  """

  def __init__(self) -> None:
    # Set Windows Application User Model ID for clean Taskbar icon grouping
    if os.name == "nt":
      try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TKSEngine.Automation.Studio.2.0")
      except Exception:
        pass

  def run(self) -> None:
    # 1. Configure Playwright browser location before any launch
    configure_playwright_environment()

    # 2. Resolve writable config and storage
    config_path = resolve_config_path()
    config = ConfigManager(config_path)
    bundle_dir = get_app_bundle_dir()
    user_data_dir = get_user_data_dir()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)

    # 3. Crash logging hook pointing to user logs directory
    def _global_excepthook(exc_type, exc_value, exc_traceback) -> None:
      import traceback
      err = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
      log_path = get_logs_dir() / "crash.log"
      try:
        with open(log_path, "a", encoding="utf-8") as f:
          f.write(err + "\n")
      except Exception:
        pass
      print("CRASH DETECTED:\n", err, file=sys.stderr)

    sys.excepthook = _global_excepthook

    # 4. Set application icon
    ico_candidates = [
      bundle_dir / "assets" / "tks_engine.ico",
      bundle_dir / "assets" / "icon.ico",
    ]
    for ico_path in ico_candidates:
      if ico_path.exists():
        app.setWindowIcon(QIcon(str(ico_path)))
        break

    # 5. First-Run Setup Wizard (only on fresh installation)
    initialized_marker = get_storage_dir() / ".initialized"
    if not initialized_marker.exists():
      dlg = FirstRunDialog()
      dlg.exec()

    # 6. Initialize Theme Manager
    theme_manager = ThemeManager(
      app=app,
      initial_mode=config.theme,
      accent_color=config.primary_color,
    )

    # 7. Create Main Window
    from gui.pages.auto_operations_window import AutoOperationsMainWindow

    if "--wizard" in sys.argv:
      window = MainWindow(theme_manager=theme_manager)
      w, h = config.window_size
      window.resize(w, h)
      mw, mh = config.min_window_size
      window.setMinimumSize(mw, mh)
      GUIController(window, config, project_root=user_data_dir)
    else:
      window = AutoOperationsMainWindow(theme_manager=theme_manager)
      w, h = 1180, 780
      window.resize(w, h)
      window.setMinimumSize(960, 640)

    screen = app.primaryScreen()
    if screen:
      avail = screen.availableGeometry()
      cx = avail.x() + max(0, (avail.width() - w) // 2)
      cy = avail.y() + max(0, (avail.height() - h) // 2)
      window.move(cx, cy)

    # 9. Show window
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
  Application().run()
