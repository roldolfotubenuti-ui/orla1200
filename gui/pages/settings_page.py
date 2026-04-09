from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.widgets.cards import SurfaceCard


class SettingsPage(PageLayout):
  """Appearance settings page.

  :param icon_color: Accent color used for icons.
  :return: None
  """

  TITLE = "Settings"
  DESCRIPTION = "Choose a single application theme from the theme dropdown."

  def __init__(self, icon_color: str) -> None:
    """Initialize the settings page.

    :param icon_color: Accent color used for icons.
    :return: None
    """
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    """Build the settings page UI.

    :return: None
    """
    theme_card = SurfaceCard()
    theme_layout = QVBoxLayout(theme_card)
    theme_layout.setContentsMargins(18, 18, 18, 18)
    theme_layout.setSpacing(12)
    theme_layout.addWidget(SectionHeader(
      "Theme Settings",
      "Theme changes are controlled only from this tab. Choose the palette that best fits your workflow.",
      "fa5s.palette",
      self._icon_color,
    ))

    title = QLabel("Application theme")
    title.setProperty("class", "section-title")
    theme_layout.addWidget(title)

    self.theme_mode_combo = QComboBox()
    self.theme_mode_combo.setMaximumWidth(240)
    self.theme_mode_combo.addItems([
      "Dark",
      "Light",
      "Orange",
      "Ocean",
      "Forest",
      "Slate",
      "Rose",
    ])
    theme_layout.addWidget(self.theme_mode_combo)
    self.content_layout.addWidget(theme_card)

    info_card = SurfaceCard(class_name="muted-card")
    info_layout = QVBoxLayout(info_card)
    info_layout.setContentsMargins(18, 18, 18, 18)
    info_layout.setSpacing(10)
    info_layout.addWidget(SectionHeader(
      "Theme Reference",
      "Included themes remain optimized for a clean desktop productivity layout.",
      "fa5s.info-circle",
      self._icon_color,
    ))
    note = QLabel(
      "Included themes: Dark, Light, Orange, Ocean, Forest, Slate, and Rose."
    )
    note.setProperty("class", "muted")
    note.setWordWrap(True)
    info_layout.addWidget(note)
    self.content_layout.addWidget(info_card)
    self.content_layout.addStretch(1)
