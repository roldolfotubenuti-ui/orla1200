from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication


_FONT_FILES: dict[str, list[str]] = {
  "Inter": [
    "Inter-Regular.ttf",
    "Inter Variable.ttf",
    "InterVariable.ttf",
  ],
  "Noto Sans": [
    "NotoSans-Regular.ttf",
    "NotoSans.ttf",
  ],
  "IBM Plex Sans": [
    "IBMPlexSans-Regular.ttf",
    "BlexSans-Regular.ttf",
  ],
}


def load_app_font(app: QApplication) -> str:
  """Load the best available modern UI font.

  :param app: Running QApplication instance.
  :return: Resolved font family name.
  """
  fonts_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"

  for family, files in _FONT_FILES.items():
    for filename in files:
      font_path = fonts_dir / filename
      if not font_path.exists():
        continue
      font_id = QFontDatabase.addApplicationFont(str(font_path))
      if font_id < 0:
        continue
      families = QFontDatabase.applicationFontFamilies(font_id)
      if families:
        resolved = families[0]
        app.setFont(QFont(resolved, 10))
        return resolved

  available_families = QFontDatabase.families()
  for family in ("Inter", "Noto Sans", "IBM Plex Sans", "Segoe UI"):
    if family in available_families:
      app.setFont(QFont(family, 10))
      return family

  fallback = app.font().family()
  app.setFont(QFont(fallback, 10))
  return fallback
