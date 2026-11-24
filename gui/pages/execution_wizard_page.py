from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
  QCheckBox,
  QComboBox,
  QHBoxLayout,
  QLabel,
  QProgressBar,
  QPushButton,
  QVBoxLayout,
  QWidget,
)

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.pages.accounts_page import InlineStat
from gui.tables.video_table import VideoTable
from gui.theme.palette import ThemePalette
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon
from gui.widgets.mac_terminal import MacTerminalPanel


class ExecutionWizardPage(PageLayout):
  """Wizard Step 5: Exclusive execution dashboard, real-time queue statuses, controls, and terminal."""

  TITLE = "5. Executar Publicações"
  DESCRIPTION = "Painel exclusivo de execução: inicie, pause, retome ou interrompa a fila e acompanhe os logs em tempo real."

  back_requested = pyqtSignal()

  def __init__(self, icon_color: str, palette: ThemePalette) -> None:
    super().__init__()
    self._icon_color = icon_color
    self._palette = palette
    self._build_ui()

  def _build_ui(self) -> None:
    dashboard_card = SurfaceCard()
    dash_layout = QVBoxLayout(dashboard_card)
    dash_layout.setContentsMargins(20, 18, 20, 18)
    dash_layout.setSpacing(14)
    dash_layout.addWidget(SectionHeader(
      "ETAPA 5 — PAINEL DE EXECUÇÃO E PUBLICAÇÃO",
      "A fila está confirmada e pronta. A publicação só iniciará quando você clicar explicitamente em EXECUTE.",
      "fa5s.rocket",
      self._icon_color,
    ))

    # Visual KPI Metrics Row
    metrics_row = QHBoxLayout()
    metrics_row.setSpacing(28)
    self.metric_account = InlineStat("Conta Selecionada", "-", "Perfil ativo")
    self.metric_total = InlineStat("Total de Vídeos", "0", "Na campanha")
    self.metric_pending = InlineStat("Pendentes", "0", "Aguardando envio")
    self.metric_scheduled = InlineStat("Agendadas", "0", "Programadas no TikTok")
    self.metric_published = InlineStat("Concluídas", "0", "Publicadas")
    self.metric_failed = InlineStat("Com Erro", "0", "Falhas / Atenção")

    for m in (
      self.metric_account,
      self.metric_total,
      self.metric_pending,
      self.metric_scheduled,
      self.metric_published,
      self.metric_failed,
    ):
      metrics_row.addWidget(m)
    metrics_row.addStretch(1)
    dash_layout.addLayout(metrics_row)

    # Progress Bar Strip
    prog_row = QHBoxLayout()
    prog_row.setSpacing(12)
    self.progress_bar = QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setTextVisible(False)
    self.progress_bar.setFixedHeight(14)
    prog_row.addWidget(self.progress_bar, 1)

    self.progress_label = QLabel("0%")
    self.progress_label.setProperty("class", "section-title")
    prog_row.addWidget(self.progress_label)

    self.success_label = QLabel("Success 0")
    self.success_label.setProperty("class", "muted")
    prog_row.addWidget(self.success_label)

    self.failure_label = QLabel("Failed 0")
    self.failure_label.setProperty("class", "muted")
    prog_row.addWidget(self.failure_label)
    dash_layout.addLayout(prog_row)

    # Controls Bar: EXECUTE, PAUSE, RESUME, STOP, LOGS + Headless/Retry toggles
    controls_row = QHBoxLayout()
    controls_row.setSpacing(10)

    self.start_btn = QPushButton(" EXECUTE")
    self.start_btn.setProperty("class", "accent")
    self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.start_btn.setIcon(build_icon("fa5s.play", "#ffffff"))
    self.start_btn.setEnabled(False)
    controls_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton(" PAUSE")
    self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pause_btn.setIcon(build_icon("fa5s.pause", self._icon_color))
    self.pause_btn.setEnabled(False)
    controls_row.addWidget(self.pause_btn)

    self.resume_btn = QPushButton(" RESUME")
    self.resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.resume_btn.setIcon(build_icon("fa5s.play-circle", "#22c55e"))
    self.resume_btn.setEnabled(False)
    controls_row.addWidget(self.resume_btn)

    self.stop_btn = QPushButton(" STOP")
    self.stop_btn.setProperty("class", "danger")
    self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.stop_btn.setIcon(build_icon("fa5s.stop", "#ffffff"))
    self.stop_btn.setEnabled(False)
    controls_row.addWidget(self.stop_btn)

    self.logs_btn = QPushButton(" LOGS")
    self.logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.logs_btn.setIcon(build_icon("fa5s.terminal", self._icon_color))
    controls_row.addWidget(self.logs_btn)

    self.export_btn = QPushButton(" Exportar Relatório")
    self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.export_btn.setIcon(build_icon("fa5s.file-export", self._icon_color))
    controls_row.addWidget(self.export_btn)

    controls_row.addSpacing(12)
    self.headless_check = QCheckBox("Headless (Navegador oculto)")
    controls_row.addWidget(self.headless_check)

    self.retry_check = QCheckBox("Retry failures")
    controls_row.addWidget(self.retry_check)

    controls_row.addStretch(1)

    self.back_btn = QPushButton("← Voltar para Revisão")
    self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.back_btn.clicked.connect(self.back_requested.emit)
    controls_row.addWidget(self.back_btn)

    dash_layout.addLayout(controls_row)

    # Hidden compatibility controls for controller aliases
    self.account_dropdown = QComboBox()
    self.account_dropdown.hide()
    self.random_account_btn = QPushButton()
    self.random_account_btn.hide()
    self.file_count_label = QLabel("")
    self.file_count_label.hide()

    self.content_layout.addWidget(dashboard_card)

    # Queue Status Table
    table_card = SurfaceCard()
    table_layout = QVBoxLayout(table_card)
    table_layout.setContentsMargins(20, 16, 20, 16)
    table_layout.setSpacing(10)

    filter_row = QHBoxLayout()
    filter_row.setSpacing(14)
    self.filter_pending_check = QCheckBox("Pending")
    self.filter_pending_check.setChecked(True)
    self.filter_scheduled_check = QCheckBox("Scheduled")
    self.filter_scheduled_check.setChecked(True)
    self.filter_published_check = QCheckBox("Published")
    self.filter_published_check.setChecked(True)
    self.filter_failed_check = QCheckBox("Failed")
    self.filter_failed_check.setChecked(True)
    filter_row.addWidget(self.filter_pending_check)
    filter_row.addWidget(self.filter_scheduled_check)
    filter_row.addWidget(self.filter_published_check)
    filter_row.addWidget(self.filter_failed_check)
    filter_row.addStretch(1)

    self.video_total_label = QLabel("Total: 0")
    self.video_total_label.setProperty("class", "muted")
    self.video_selected_label = QLabel("Selected: 0")
    self.video_selected_label.setProperty("class", "muted")
    filter_row.addWidget(self.video_total_label)
    filter_row.addWidget(self.video_selected_label)
    table_layout.addLayout(filter_row)

    self.video_table = VideoTable(read_only=False)
    self.video_table.setMinimumHeight(250)
    table_layout.addWidget(self.video_table, 1)
    self.content_layout.addWidget(table_card, 1)

    # Live Terminal Panel
    terminal_wrap = SurfaceCard(class_name="muted-card")
    t_lay = QVBoxLayout(terminal_wrap)
    t_lay.setContentsMargins(10, 10, 10, 10)
    t_lay.setSpacing(0)
    self.terminal_panel = MacTerminalPanel(self._palette, title="Live terminal")
    self.log_panel = self.terminal_panel.log_view
    self.toggle_log_btn = self.terminal_panel.open_logs_button
    self.log_clear_button = self.terminal_panel.clear_button
    self.logs_btn.clicked.connect(self.toggle_log_btn.click)
    t_lay.addWidget(self.terminal_panel, 1)
    self.content_layout.addWidget(terminal_wrap, 1)

  def set_palette_data(self, palette: ThemePalette) -> None:
    self._palette = palette
    self.terminal_panel.set_palette_data(palette)
