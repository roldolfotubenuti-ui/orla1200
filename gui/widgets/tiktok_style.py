from __future__ import annotations

"""Design tokens and shared stylesheet for the TikTok Studio–style screens.

Only visual constants live here. No backend / automation logic.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from gui.widgets.icon import build_icon

TT_RED = "#FE2C55"
TT_RED_HOVER = "#E8264C"
TT_RED_DISABLED = "#FFB3C2"
TT_BG = "#FFFFFF"
TT_BG_ALT = "#F7F7F7"
TT_BG_HOVER = "#F1F1F2"
TT_BORDER = "#E5E5E5"
TT_TEXT = "#161823"
TT_TEXT_2 = "#8A8A8A"
TT_TEXT_DISABLED = "#C4C4C4"
TT_GREEN = "#20B26C"
TT_FONT = '"TikTok Sans", "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif'


def tt_base_stylesheet() -> str:
  """Stylesheet applied to the root of every TikTok Studio–style widget.

  Every property that the global app theme could set is redefined here so the
  global (blue) theme never leaks into these screens.
  """
  return f"""
    QWidget {{
      font-family: {TT_FONT};
      color: {TT_TEXT};
      font-size: 13px;
    }}
    QLabel {{ background: transparent; border: none; padding: 0; }}
    QToolTip {{
      background: {TT_TEXT}; color: #FFFFFF; border: none; padding: 4px 8px; border-radius: 4px;
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #D6D6D6; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: #BDBDBD; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: none; }}
    QScrollBar:horizontal {{ height: 0; }}

    QPushButton {{
      background: transparent; border: none; border-radius: 4px;
      padding: 0; margin: 0; min-height: 0; min-width: 0; color: {TT_TEXT};
      text-align: center;
    }}
    QPushButton#ttPrimary {{
      background: {TT_RED}; color: #FFFFFF; font-size: 14px; font-weight: 600;
      border-radius: 4px; padding: 0 24px; min-height: 36px;
    }}
    QPushButton#ttPrimary:hover {{ background: {TT_RED_HOVER}; }}
    QPushButton#ttPrimary:disabled {{ background: {TT_RED_DISABLED}; color: #FFFFFF; }}
    QPushButton#ttSecondary {{
      background: {TT_BG_HOVER}; color: {TT_TEXT}; font-size: 13px; font-weight: 600;
      border-radius: 4px; padding: 0 14px; min-height: 32px;
    }}
    QPushButton#ttSecondary:hover {{ background: #E3E3E4; }}
    QPushButton#ttSecondary:disabled {{ color: {TT_TEXT_DISABLED}; }}
    QPushButton#ttPillGray {{
      background: {TT_BG_HOVER}; color: {TT_TEXT}; font-size: 13px; font-weight: 600;
      border-radius: 14px; padding: 0 16px; min-height: 28px;
    }}
    QPushButton#ttPillGray:hover {{ background: #E3E3E4; }}
    QPushButton#ttPillRed {{
      background: {TT_RED}; color: #FFFFFF; font-size: 13px; font-weight: 600;
      border-radius: 14px; padding: 0 16px; min-height: 28px;
    }}
    QPushButton#ttPillRed:hover {{ background: {TT_RED_HOVER}; }}
    QPushButton#ttIconBtn {{ border-radius: 4px; min-width: 28px; min-height: 28px; max-width: 28px; max-height: 28px; }}
    QPushButton#ttIconBtn:hover {{ background: {TT_BG_HOVER}; }}
    QPushButton#ttChip {{ border-radius: 4px; padding: 0 6px; min-height: 28px; text-align: left; }}
    QPushButton#ttChip:hover {{ background: {TT_BG_HOVER}; }}
    QPushButton#ttLink {{ color: {TT_RED}; font-size: 12px; font-weight: 600; text-align: left; }}
    QPushButton#ttLink:hover {{ text-decoration: underline; }}

    QMenu {{
      background: #FFFFFF; border: 1px solid {TT_BORDER}; border-radius: 8px; padding: 6px 0;
    }}
    QMenu::item {{ padding: 8px 28px 8px 14px; color: {TT_TEXT}; font-size: 13px; background: transparent; }}
    QMenu::item:selected {{ background: {TT_BG_HOVER}; }}
    QMenu::item:disabled {{ color: {TT_TEXT_DISABLED}; }}
    QMenu::icon {{ padding-left: 10px; }}

    QLineEdit, QTextEdit, QPlainTextEdit {{
      background: #FFFFFF; color: {TT_TEXT}; border: 1px solid {TT_BORDER}; border-radius: 6px;
      padding: 6px 8px; font-size: 13px; selection-background-color: #FFD6DE; selection-color: {TT_TEXT};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 1px solid #A6A6A6; }}
    QComboBox, QSpinBox {{
      background: #FFFFFF; color: {TT_TEXT}; border: 1px solid {TT_BORDER}; border-radius: 4px;
      padding: 4px 8px; min-height: 24px;
    }}
    QComboBox QAbstractItemView {{ background: #FFFFFF; color: {TT_TEXT}; selection-background-color: {TT_BG_HOVER}; selection-color: {TT_TEXT}; }}
  """


def hline(color: str = TT_BORDER) -> QFrame:
  line = QFrame()
  line.setFixedHeight(1)
  line.setStyleSheet(f"background: {color}; border: none;")
  return line


def vline(color: str = TT_BORDER) -> QFrame:
  line = QFrame()
  line.setFixedWidth(1)
  line.setStyleSheet(f"background: {color}; border: none;")
  return line


class ChipButton(QPushButton):
  """Flat TikTok-style dropdown control: [icon] text [chevron].

  Child labels ignore mouse events, so clicks reach the button.
  """

  def __init__(
    self,
    icon_name: str,
    text: str,
    chevron: bool = True,
    bold: bool = False,
    parent: QWidget | None = None,
  ) -> None:
    super().__init__(parent)
    self.setObjectName("ttChip")
    self.setCursor(Qt.CursorShape.PointingHandCursor)
    self.setFixedHeight(30)

    layout = QHBoxLayout(self)
    layout.setContentsMargins(6, 0, 8, 0)
    layout.setSpacing(6)

    self._icon_lbl = QLabel()
    self._icon_name = icon_name
    self._icon_lbl.setPixmap(build_icon(icon_name, TT_TEXT).pixmap(13, 13))
    self._icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    layout.addWidget(self._icon_lbl)

    self._text_lbl = QLabel(text)
    self._text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    self._text_lbl.setStyleSheet(f"font-size: 13px; font-weight: {700 if bold else 600}; color: {TT_TEXT};")
    layout.addWidget(self._text_lbl)

    self._chev_lbl = QLabel()
    self._chev_lbl.setPixmap(build_icon("fa5s.chevron-down", TT_TEXT).pixmap(8, 8))
    self._chev_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    self._chev_lbl.setVisible(chevron)
    layout.addWidget(self._chev_lbl)
    layout.addStretch(1)

  def set_label(self, text: str, bold: bool = False) -> None:
    self._text_lbl.setText(text)
    self._text_lbl.setStyleSheet(f"font-size: 13px; font-weight: {700 if bold else 600}; color: {TT_TEXT};")
    self.updateGeometry()
    self.adjustSize()

  def label(self) -> str:
    return self._text_lbl.text()

  def text(self) -> str:  # noqa: D401 - keep QPushButton-like API for tests
    return self._text_lbl.text()

  def set_icon_name(self, icon_name: str) -> None:
    self._icon_name = icon_name
    self._icon_lbl.setPixmap(build_icon(icon_name, TT_TEXT).pixmap(13, 13))
    self.updateGeometry()

  def sizeHint(self) -> QSize:
    try:
      if self.layout() is not None:
        hint = self.layout().sizeHint()
        return QSize(max(hint.width(), self.minimumWidth()), max(30, hint.height()))
    except Exception:
      pass
    return super().sizeHint()

  def minimumSizeHint(self) -> QSize:
    try:
      if self.layout() is not None:
        hint = self.layout().minimumSize()
        return QSize(max(hint.width(), self.minimumWidth()), max(30, hint.height()))
    except Exception:
      pass
    return super().minimumSizeHint()
