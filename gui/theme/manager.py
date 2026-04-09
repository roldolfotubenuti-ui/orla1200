from __future__ import annotations

from PyQt6.QtCore import QObject, QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication

from gui.theme.fonts import load_app_font
from gui.theme.palette import ThemePalette, build_palette
from gui.theme.stylesheet import build_stylesheet


class ThemeManager(QObject):
  """Manage palette selection and stylesheet updates.

  :param app: Running QApplication instance.
  :param initial_mode: Initial theme identifier.
  :param accent_color: Fallback accent color for dark and light themes.
  :return: None
  """

  theme_changed = pyqtSignal(str)

  AVAILABLE_THEMES: list[tuple[str, str]] = [
    ("Dark", "dark"),
    ("Light", "light"),
    ("Orange", "orange"),
    ("Ocean", "ocean"),
    ("Forest", "forest"),
    ("Slate", "slate"),
    ("Rose", "rose"),
  ]

  _MODE_MAP = {
    "dark": "dark",
    "light": "light",
    "orange": "orange",
    "ocean": "ocean",
    "forest": "forest",
    "slate": "slate",
    "rose": "rose",
    "system": "system",
    "default": "system",
    "neumorphism_dark": "dark",
    "neumorphism_light": "light",
  }

  def __init__(
    self,
    app: QApplication,
    initial_mode: str = "dark",
    accent_color: str = "#2563eb",
  ) -> None:
    """Initialize the theme manager.

    :param app: Running QApplication instance.
    :param initial_mode: Initial theme identifier.
    :param accent_color: Fallback accent color for dark and light themes.
    :return: None
    """
    super().__init__()
    self._app = app
    self._settings = QSettings("TikTokScheduler", "DesktopUI")
    self._font_family = load_app_font(app)
    self._accent_color = accent_color
    stored_mode = self._settings.value("theme_mode", initial_mode, str)
    self._mode = self._normalize_mode(stored_mode)
    self._palette = build_palette(self._mode, self._accent_color)
    self.apply_theme(self._mode)

  @property
  def mode(self) -> str:
    """Return the active theme identifier.

    :return: Theme identifier.
    """
    return self._mode

  @property
  def resolved_mode(self) -> str:
    """Return the resolved theme identifier.

    :return: Theme identifier.
    """
    return self._mode

  @property
  def palette(self) -> ThemePalette:
    """Return the active theme palette.

    :return: Active palette.
    """
    return self._palette

  def apply_theme(self, mode: str) -> None:
    """Apply a theme and refresh the application stylesheet.

    :param mode: Desired theme identifier.
    :return: None
    """
    self._mode = self._normalize_mode(mode)
    self._settings.setValue("theme_mode", self._mode)
    self._palette = build_palette(self._mode, self._accent_color)
    self._app.setStyleSheet(build_stylesheet(self._palette, self._font_family))
    self.theme_changed.emit(self._mode)

  def theme_label(self, mode: str | None = None) -> str:
    """Return the visible label for a theme identifier.

    :param mode: Optional theme identifier.
    :return: Human-readable theme label.
    """
    target_mode = self._normalize_mode(mode or self._mode)
    for label, value in self.AVAILABLE_THEMES:
      if value == target_mode:
        return label
    return "Dark"

  def _normalize_mode(self, mode: str) -> str:
    """Normalize theme identifiers and resolve legacy system mode.

    :param mode: Raw theme identifier.
    :return: Normalized theme identifier.
    """
    normalized = self._MODE_MAP.get(str(mode).strip().lower(), "dark")
    if normalized == "system":
      return self._system_default_theme()
    return normalized

  def _system_default_theme(self) -> str:
    """Resolve the legacy system theme to dark or light.

    :return: ``dark`` or ``light``.
    """
    try:
      scheme = self._app.styleHints().colorScheme()
    except AttributeError:
      return "light"
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"
