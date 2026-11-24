from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
  QFrame,
  QHBoxLayout,
  QLabel,
  QProgressBar,
  QPushButton,
  QVBoxLayout,
  QWidget,
)

from gui.widgets.icon import build_icon
from gui.widgets.tiktok_style import (
  TT_BG_HOVER,
  TT_BORDER,
  TT_FONT,
  TT_GREEN,
  TT_RED,
  TT_TEXT,
  TT_TEXT_2,
)


class WizardStepperBar(QFrame):
  """Top progress stepper bar for the 3-stage TKS Engine 2.0 workflow.

  Displays:
  1. CONTA -> 2. ESTÚDIO TIKTOK -> 3. PUBLICAÇÃO
  with active step indicator in TikTok Red (#FE2C55), smooth red progress bar,
  active account chip, and quick access to Logs and Theme Settings.
  """

  step_clicked = pyqtSignal(int)
  open_logs_requested = pyqtSignal()
  open_settings_requested = pyqtSignal()

  STEPS: list[tuple[int, str, str, str]] = [
    (0, "1. CONTA", "Escolher perfil TikTok", "fa5s.user"),
    (1, "2. ESTÚDIO TIKTOK", "Carregar e agendar vídeos", "fa5s.cloud-upload-alt"),
    (2, "3. PUBLICAÇÃO", "Executar fila e monitorar", "fa5s.rocket"),
  ]

  def __init__(self, accent_color: str = TT_RED, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self._accent_color = TT_RED
    self._current_step = 0
    self._step_buttons: list[QPushButton] = []
    self.setFixedHeight(68)
    self.setStyleSheet(f"""
      WizardStepperBar {{
        background-color: #FFFFFF;
        border-bottom: 1px solid {TT_BORDER};
        font-family: {TT_FONT};
      }}
      QLabel {{
        background: transparent;
        font-family: {TT_FONT};
      }}
      QPushButton#stepperLogsBtn, QPushButton#stepperSettingsBtn {{
        background-color: {TT_BG_HOVER};
        color: {TT_TEXT};
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 600;
        border: none;
      }}
      QPushButton#stepperLogsBtn:hover, QPushButton#stepperSettingsBtn:hover {{
        background-color: #E3E3E4;
      }}
      QProgressBar {{
        background: #F1F1F2;
        border: none;
        border-radius: 2px;
      }}
      QProgressBar::chunk {{
        background: {TT_RED};
        border-radius: 2px;
      }}
    """)

    root_layout = QVBoxLayout(self)
    root_layout.setContentsMargins(24, 10, 24, 8)
    root_layout.setSpacing(8)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(10)

    brand_label = QLabel("TKS ENGINE 2.0")
    brand_label.setStyleSheet(
      "font-size: 15px; font-weight: 800; letter-spacing: 0.5px; color: #161823;"
    )
    top_row.addWidget(brand_label)

    self.active_account_badge = QLabel("Conta: Nenhuma selecionada")
    self.active_account_badge.setStyleSheet(
      f"background: {TT_BG_HOVER}; color: {TT_TEXT_2}; font-size: 12px; font-weight: 600; "
      "border-radius: 12px; padding: 2px 10px;"
    )
    top_row.addWidget(self.active_account_badge)

    top_row.addStretch(1)

    steps_row = QHBoxLayout()
    steps_row.setContentsMargins(0, 0, 0, 0)
    steps_row.setSpacing(6)

    for idx, short_title, tooltip, icon_name in self.STEPS:
      btn = QPushButton(f" {short_title}")
      btn.setToolTip(tooltip)
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      btn.clicked.connect(lambda _checked=False, step_idx=idx: self.step_clicked.emit(step_idx))
      self._step_buttons.append(btn)
      steps_row.addWidget(btn)

      if idx < len(self.STEPS) - 1:
        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 14px; font-weight: 600; padding: 0 4px;")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        steps_row.addWidget(arrow)

    top_row.addLayout(steps_row)
    top_row.addStretch(1)

    self.top_logs_btn = QPushButton(" Logs")
    self.top_logs_btn.setObjectName("stepperLogsBtn")
    self.top_logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.top_logs_btn.setIcon(build_icon("fa5s.terminal", TT_TEXT))
    self.top_logs_btn.clicked.connect(self.open_logs_requested.emit)
    top_row.addWidget(self.top_logs_btn)

    self.top_settings_btn = QPushButton()
    self.top_settings_btn.setObjectName("stepperSettingsBtn")
    self.top_settings_btn.setToolTip("Tema e Configurações")
    self.top_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.top_settings_btn.setIcon(build_icon("fa5s.palette", TT_TEXT))
    self.top_settings_btn.clicked.connect(self.open_settings_requested.emit)
    top_row.addWidget(self.top_settings_btn)

    root_layout.addLayout(top_row)

    self.step_progress_bar = QProgressBar()
    self.step_progress_bar.setRange(0, 100)
    self.step_progress_bar.setValue(33)
    self.step_progress_bar.setTextVisible(False)
    self.step_progress_bar.setFixedHeight(4)
    root_layout.addWidget(self.step_progress_bar)

    self.set_current_step(0)

  def set_current_step(self, step_index: int) -> None:
    """Update the visual state of the stepper for the active step.

    :param step_index: Step index (0..2).
    """
    self._current_step = max(0, min(len(self.STEPS) - 1, step_index))
    progress_pct = int(((self._current_step + 1) / len(self.STEPS)) * 100)
    self.step_progress_bar.setValue(progress_pct)

    for idx, btn in enumerate(self._step_buttons):
      _i, short_title, _tip, icon_name = self.STEPS[idx]
      if idx == self._current_step:
        btn.setProperty("class", "accent")
        btn.setIcon(build_icon(icon_name, "#FFFFFF"))
        btn.setStyleSheet(f"""
          QPushButton {{
            background-color: {TT_RED};
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 700;
            border-radius: 6px;
            padding: 6px 14px;
            border: none;
          }}
          QPushButton:hover {{
            background-color: #E8264C;
          }}
        """)
      elif idx < self._current_step:
        btn.setProperty("class", "")
        btn.setIcon(build_icon("fa5s.check-circle", TT_GREEN))
        btn.setStyleSheet(f"""
          QPushButton {{
            background-color: {TT_BG_HOVER};
            color: {TT_TEXT};
            font-size: 13px;
            font-weight: 600;
            border-radius: 6px;
            padding: 6px 14px;
            border: none;
          }}
          QPushButton:hover {{
            background-color: #E3E3E4;
          }}
        """)
      else:
        btn.setProperty("class", "ghost")
        btn.setIcon(build_icon(icon_name, TT_TEXT_2))
        btn.setStyleSheet(f"""
          QPushButton {{
            background-color: transparent;
            color: {TT_TEXT};
            font-size: 13px;
            font-weight: 500;
            border-radius: 6px;
            padding: 6px 14px;
            border: none;
          }}
          QPushButton:hover {{
            background-color: {TT_BG_HOVER};
          }}
        """)
      btn.style().unpolish(btn)
      btn.style().polish(btn)

  def set_active_account(self, username: str) -> None:
    """Update the active account badge in the top bar.

    :param username: Selected TikTok username.
    """
    if username:
      self.active_account_badge.setText(f"@{username}")
      self.active_account_badge.setProperty("role", "published")
      self.active_account_badge.setStyleSheet(
        "background: #E6F9EE; color: #00B649; font-size: 12px; font-weight: 700; "
        "border-radius: 12px; padding: 2px 10px;"
      )
    else:
      self.active_account_badge.setText("Conta: Nenhuma selecionada")
      self.active_account_badge.setProperty("role", "pending")
      self.active_account_badge.setStyleSheet(
        f"background: {TT_BG_HOVER}; color: {TT_TEXT_2}; font-size: 12px; font-weight: 600; "
        "border-radius: 12px; padding: 2px 10px;"
      )
    self.active_account_badge.style().unpolish(self.active_account_badge)
    self.active_account_badge.style().polish(self.active_account_badge)
