from __future__ import annotations

from gui.theme.palette import ThemePalette


def build_stylesheet(palette: ThemePalette, font_family: str) -> str:
  """Build the global application stylesheet.

  :param palette: Active palette tokens.
  :param font_family: Preferred application font family.
  :return: Complete QSS stylesheet.
  """
  return f"""
    QMainWindow, QDialog {{
      background-color: {palette.window_bg};
    }}

    QWidget#main-central,
    QTabWidget[class="workspace-tabs"] {{
      background-color: {palette.window_bg};
    }}

    QWidget[class="page"],
    QWidget[class="page-viewport"],
    QWidget[class="page-content"] {{
      background-color: {palette.surface};
    }}

    QWidget {{
      color: {palette.text_primary};
      font-family: "{font_family}", "Segoe UI", sans-serif;
      font-size: 13px;
    }}

    QWidget[class="page"] {{
      background-color: {palette.surface};
    }}

    QWidget[class="sidebar"] {{
      background-color: {palette.sidebar_bg};
      border-right: 1px solid {palette.border};
    }}

    QWidget[class="topbar"] {{
      background-color: {palette.topbar_bg};
      border-bottom: 1px solid {palette.border};
    }}

    QWidget[class="status-strip"] {{
      background-color: {palette.surface_alt};
      border-top: 1px solid {palette.border};
    }}

    QTabWidget[class="workspace-tabs"]::pane {{
      border: 1px solid {palette.border};
      border-top: none;
      background-color: {palette.surface};
      top: -1px;
    }}

    QTabWidget[class="workspace-tabs"] QTabBar {{
      background-color: transparent;
      padding: 6px 24px 0px 24px;
    }}

    QTabWidget[class="workspace-tabs"] QTabBar::tab {{
      background-color: {palette.surface_alt};
      color: {palette.text_secondary};
      border: 1px solid {palette.border};
      border-bottom-color: {palette.border};
      border-radius: 0px;
      padding: 4px 12px;
      margin-top: 2px;
      margin-right: -1px;
      min-width: 0px;
      font-size: 12px;
      font-weight: 700;
    }}

    QTabWidget[class="workspace-tabs"] QTabBar::tab:hover {{
      background-color: {palette.row_hover};
      color: {palette.text_primary};
    }}

    QTabWidget[class="workspace-tabs"] QTabBar::tab:selected {{
      background-color: {palette.surface};
      color: {palette.text_primary};
      border-color: {palette.border_strong};
      border-bottom-color: {palette.surface};
      margin-top: 0px;
      padding-top: 5px;
      padding-bottom: 7px;
    }}

    QTabWidget[class="workspace-tabs"] QTabBar::tab:top:last {{
      margin-right: 0px;
    }}

    QTabWidget[class="workspace-tabs"] QTabBar::tab:!selected {{
      margin-bottom: 0px;
    }}

    QFrame[class="card"],
    QFrame[class="stat-card"],
    QFrame[class="muted-card"] {{
      background-color: {palette.surface};
      border: 1px solid {palette.border};
      border-radius: 16px;
    }}

    QFrame[class="muted-card"] {{
      background-color: {palette.surface_alt};
    }}

    QLabel {{
      background: transparent;
    }}

    QLabel[class="page-title"] {{
      font-size: 22px;
      font-weight: 700;
      color: {palette.text_primary};
    }}

    QLabel[class="page-description"],
    QLabel[class="muted"],
    QLabel[class="stat-caption"] {{
      color: {palette.text_secondary};
      font-size: 12px;
    }}

    QLabel[class="inline-stat-title"] {{
      color: {palette.text_muted};
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
    }}

    QLabel[class="inline-stat-value"] {{
      color: {palette.accent};
      font-size: 20px;
      font-weight: 700;
    }}

    QLabel[class="inline-stat-caption"] {{
      color: {palette.text_secondary};
      font-size: 12px;
    }}

    QLabel[class="section-title"] {{
      color: {palette.text_primary};
      font-size: 15px;
      font-weight: 700;
    }}

    QLabel[class="metric-value"] {{
      color: {palette.text_primary};
      font-size: 26px;
      font-weight: 700;
    }}

    QLabel[class="chip"] {{
      border-radius: 11px;
      padding: 5px 12px;
      font-size: 11px;
      font-weight: 700;
      min-height: 16px;
      qproperty-alignment: AlignCenter;
    }}

    QLabel[class="chip"][role="pending"] {{
      background-color: {palette.chip_pending_bg};
      color: {palette.chip_pending_fg};
    }}

    QLabel[class="chip"][role="scheduled"] {{
      background-color: {palette.chip_scheduled_bg};
      color: {palette.chip_scheduled_fg};
    }}

    QLabel[class="chip"][role="published"] {{
      background-color: {palette.chip_published_bg};
      color: {palette.chip_published_fg};
    }}

    QLabel[class="chip"][role="failed"] {{
      background-color: {palette.chip_failed_bg};
      color: {palette.chip_failed_fg};
    }}

    QToolButton[class="sidebar-button"] {{
      background: transparent;
      border: none;
      border-radius: 12px;
      color: {palette.text_secondary};
      font-weight: 600;
      padding: 10px 14px;
      text-align: left;
      min-height: 20px;
    }}

    QToolButton[class="sidebar-button"]:hover {{
      background-color: {palette.sidebar_hover};
      color: {palette.text_primary};
    }}

    QToolButton[class="sidebar-button"]:checked {{
      background-color: {palette.sidebar_active};
      color: {palette.text_primary};
    }}

    QPushButton, QToolButton[class="toolbar-button"] {{
      background-color: {palette.surface_alt};
      color: {palette.text_primary};
      border: 1px solid {palette.border};
      border-radius: 10px;
      padding: 8px 14px;
      min-height: 18px;
      font-weight: 600;
    }}

    QPushButton:hover, QToolButton[class="toolbar-button"]:hover {{
      background-color: {palette.row_hover};
      border-color: {palette.border_strong};
    }}

    QPushButton:pressed, QToolButton[class="toolbar-button"]:pressed {{
      background-color: {palette.surface_muted};
    }}

    QPushButton:disabled {{
      color: {palette.text_muted};
      background-color: {palette.surface_muted};
      border-color: {palette.border};
    }}

    QPushButton[class="accent"] {{
      background-color: {palette.accent};
      border: 1px solid {palette.accent};
      color: {palette.text_on_accent};
    }}

    QPushButton[class="accent"]:hover {{
      background-color: {palette.accent_hover};
      border-color: {palette.accent_hover};
    }}

    QPushButton[class="accent"]:pressed {{
      background-color: {palette.accent_pressed};
      border-color: {palette.accent_pressed};
    }}

    QPushButton[class="danger"] {{
      background-color: {palette.error};
      border-color: {palette.error};
      color: {palette.text_on_accent};
    }}

    QPushButton[class="ghost"] {{
      background-color: transparent;
      color: {palette.text_secondary};
    }}

    QPushButton[class="terminal-action"] {{
      background-color: transparent;
      color: {palette.text_primary};
      border: 1px solid {palette.terminal_border};
      border-radius: 8px;
      padding: 6px 12px;
      min-height: 14px;
      font-size: 12px;
      font-weight: 600;
    }}

    QPushButton[class="terminal-action"]:hover {{
      background-color: {palette.row_hover};
      border-color: {palette.border_strong};
    }}

    QPushButton[class="terminal-action"]:pressed {{
      background-color: {palette.surface_alt};
    }}

    QPushButton[class="icon-button"] {{
      min-width: 34px;
      max-width: 34px;
      min-height: 34px;
      max-height: 34px;
      padding: 0px;
    }}

    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QComboBox,
    QDateEdit,
    QSpinBox {{
      background-color: {palette.surface_alt};
      color: {palette.text_primary};
      border: 1px solid {palette.border};
      border-radius: 10px;
      padding: 8px 12px;
      selection-background-color: {palette.accent};
      selection-color: {palette.text_on_accent};
    }}

    QTextEdit, QPlainTextEdit {{
      padding: 10px 12px;
    }}

    QPlainTextEdit[class="log-view"],
    QTextEdit[class="log-view"] {{
      background-color: {palette.surface_muted};
      border: 1px solid {palette.border};
      font-family: "Cascadia Code", "Consolas", monospace;
      font-size: 12px;
    }}

    QPlainTextEdit[class="log-view"][surface="terminal"],
    QTextEdit[class="log-view"][surface="terminal"] {{
      background-color: {palette.terminal_bg};
      color: {palette.terminal_text};
      border: none;
      border-bottom-left-radius: 18px;
      border-bottom-right-radius: 18px;
      padding: 14px 16px;
      selection-background-color: {palette.border_strong};
    }}

    QLineEdit:focus,
    QTextEdit:focus,
    QPlainTextEdit:focus,
    QComboBox:focus,
    QDateEdit:focus,
    QSpinBox:focus {{
      border: 1px solid {palette.accent};
    }}

    QLineEdit[state="error"],
    QTextEdit[state="error"],
    QDateEdit[state="error"] {{
      border: 1px solid {palette.error};
    }}

    QComboBox::drop-down, QDateEdit::drop-down {{
      border: none;
      width: 26px;
    }}

    QComboBox QAbstractItemView {{
      background-color: {palette.surface};
      color: {palette.text_primary};
      border: 1px solid {palette.border_strong};
      selection-background-color: {palette.row_selected};
      selection-color: {palette.text_primary};
      padding: 4px;
      outline: none;
    }}

    QCalendarWidget {{
      background-color: {palette.surface};
      color: {palette.text_primary};
      border: 1px solid {palette.border};
      border-radius: 12px;
    }}

    QCalendarWidget QWidget#qt_calendar_navigationbar {{
      background-color: {palette.surface_alt};
      border-bottom: 1px solid {palette.border};
      border-top-left-radius: 12px;
      border-top-right-radius: 12px;
    }}

    QCalendarWidget QToolButton {{
      background-color: transparent;
      color: {palette.text_primary};
      border: none;
      padding: 6px 8px;
      font-weight: 600;
    }}

    QCalendarWidget QToolButton:hover {{
      background-color: {palette.row_hover};
    }}

    QCalendarWidget QSpinBox {{
      background-color: {palette.surface};
      color: {palette.text_primary};
      border: 1px solid {palette.border};
      border-radius: 8px;
      padding: 4px 8px;
    }}

    QCalendarWidget QMenu {{
      background-color: {palette.surface};
      color: {palette.text_primary};
      border: 1px solid {palette.border};
    }}

    QCalendarWidget QAbstractItemView:enabled {{
      background-color: {palette.surface};
      color: {palette.text_primary};
      selection-background-color: {palette.accent};
      selection-color: {palette.text_on_accent};
      alternate-background-color: {palette.surface_alt};
      outline: 0;
    }}

    QCheckBox {{
      color: {palette.text_primary};
      spacing: 8px;
    }}

    QCheckBox::indicator {{
      width: 18px;
      height: 18px;
      border-radius: 6px;
      border: 1px solid {palette.border_strong};
      background-color: {palette.surface_alt};
    }}

    QCheckBox::indicator:checked {{
      background-color: {palette.accent};
      border-color: {palette.accent};
    }}

    QTableWidget {{
      background-color: {palette.surface};
      alternate-background-color: {palette.surface_alt};
      border: 1px solid {palette.border};
      border-radius: 14px;
      gridline-color: {palette.border};
      selection-background-color: {palette.row_selected};
      selection-color: {palette.text_primary};
    }}

    QTableWidget::viewport {{
      background-color: {palette.surface};
    }}

    QTableWidget::item {{
      padding: 6px 10px;
      border-bottom: 1px solid {palette.border};
    }}

    QTableWidget::item:hover {{
      background-color: {palette.row_hover};
    }}

    QHeaderView::section,
    QTableCornerButton::section {{
      background-color: {palette.surface_alt};
      color: {palette.text_secondary};
      border: none;
      border-bottom: 1px solid {palette.border};
      padding: 8px 10px;
      font-size: 12px;
      font-weight: 700;
    }}

    QTableWidget[class="grid-table"] {{
      border-radius: 12px;
      gridline-color: {palette.border_strong};
    }}

    QTableWidget[class="grid-table"]::item {{
      border-right: 1px solid {palette.border};
      border-bottom: 1px solid {palette.border};
      padding: 8px 10px;
    }}

    QTableWidget[class="grid-table"] QHeaderView::section,
    QTableWidget[class="grid-table"] QTableCornerButton::section {{
      border-right: 1px solid {palette.border};
      border-bottom: 1px solid {palette.border_strong};
    }}

    QProgressBar {{
      background-color: {palette.surface_muted};
      border: 1px solid {palette.border};
      border-radius: 9px;
      padding: 0px;
      text-align: center;
      min-height: 16px;
      max-height: 16px;
      font-size: 11px;
      font-weight: 700;
      color: {palette.text_primary};
    }}

    QProgressBar::chunk {{
      background-color: {palette.accent};
      border-radius: 8px;
      margin: 0px;
    }}

    QSplitter::handle {{
      background-color: {palette.border};
    }}

    QSplitter::handle:vertical {{
      height: 4px;
    }}

    QScrollArea {{
      border: none;
      background: transparent;
    }}

    QScrollBar:vertical {{
      background: {palette.scrollbar_track};
      width: 10px;
      margin: 4px;
      border-radius: 5px;
    }}

    QScrollBar::handle:vertical {{
      background: {palette.scrollbar_thumb};
      min-height: 28px;
      border-radius: 5px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
      height: 0px;
      background: transparent;
    }}

    QScrollBar:horizontal {{
      background: {palette.scrollbar_track};
      height: 10px;
      margin: 4px;
      border-radius: 5px;
    }}

    QScrollBar::handle:horizontal {{
      background: {palette.scrollbar_thumb};
      min-width: 28px;
      border-radius: 5px;
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
      width: 0px;
      background: transparent;
    }}

    QToolTip {{
      color: {palette.text_primary};
      background-color: {palette.surface};
      border: 1px solid {palette.border};
      padding: 6px 8px;
    }}

    QFrame[class="terminal-shell"] {{
      background-color: {palette.terminal_shell};
      border: 1px solid {palette.terminal_border};
      border-radius: 18px;
    }}

    QWidget[class="terminal-header"] {{
      background-color: {palette.terminal_header};
      border-bottom: 1px solid {palette.terminal_border};
      border-top-left-radius: 18px;
      border-top-right-radius: 18px;
    }}

    QLabel[class="terminal-title"] {{
      color: {palette.text_primary};
      font-size: 12px;
      font-weight: 700;
    }}

    QFrame[class="terminal-dot"] {{
      border: none;
      border-radius: 5px;
    }}

    QFrame[class="terminal-dot"][role="red"] {{
      background-color: #ff5f57;
    }}

    QFrame[class="terminal-dot"][role="yellow"] {{
      background-color: #ffbd2f;
    }}

    QFrame[class="terminal-dot"][role="green"] {{
      background-color: #28c840;
    }}
  """
