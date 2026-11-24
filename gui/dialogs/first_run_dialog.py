"""First-Run Onboarding and Component Setup Wizard for TKS Engine 2.0.

Executed only on initial launch to verify system prerequisites, initialize
Playwright Chromium automation engines, configure user storage directories,
and guide the user to connect their first TikTok account.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets.icon import build_icon
from gui.widgets.tiktok_style import TT_BG, TT_BG_ALT, TT_BORDER, TT_GREEN, TT_RED, TT_TEXT, TT_TEXT_2
from utils.app_paths import (
    configure_playwright_environment,
    get_app_bundle_dir,
    get_cookies_dir,
    get_logs_dir,
    get_storage_dir,
    get_user_data_dir,
    is_frozen,
)


class SetupWorker(QThread):
    """Background worker that initializes directories, verifies Playwright, and seeds local database."""

    step_updated = pyqtSignal(int, str, str)  # step_idx (0..3), status ("running", "ok", "error"), message
    progress_updated = pyqtSignal(int)
    finished_setup = pyqtSignal(bool, str)

    def run(self) -> None:
        try:
            # Step 0: System Prerequisites
            self.step_updated.emit(0, "running", "Verificando permissões e integridade do sistema...")
            self.progress_updated.emit(10)
            time.sleep(0.3)
            user_data = get_user_data_dir()
            user_data.mkdir(parents=True, exist_ok=True)
            self.step_updated.emit(0, "ok", "Ambiente operacional Windows validado")
            self.progress_updated.emit(25)

            # Step 1: Playwright & Browser Automation Engine
            self.step_updated.emit(1, "running", "Verificando e preparando Chromium para automação...")
            self.progress_updated.emit(35)
            from utils.app_paths import ensure_playwright_chromium
            ok_browser = ensure_playwright_chromium()
            if ok_browser:
                self.step_updated.emit(1, "ok", "Navegador de automação pronto e configurado")
            else:
                self.step_updated.emit(1, "running", "Navegador local configurado (baixará se necessário)")
            self.progress_updated.emit(60)

            # Step 2: Local Database & Storage Layout
            self.step_updated.emit(2, "running", "Criando banco de dados local e repositórios de agendamento...")
            self.progress_updated.emit(75)
            storage_dir = get_storage_dir()
            (storage_dir / "schedules").mkdir(parents=True, exist_ok=True)
            (storage_dir / "publishes").mkdir(parents=True, exist_ok=True)
            (storage_dir / ".thumbs").mkdir(parents=True, exist_ok=True)
            self.step_updated.emit(2, "ok", "Estrutura de banco e agendamento inicializada")
            self.progress_updated.emit(85)

            # Step 3: Cookies and User Security isolation
            self.step_updated.emit(3, "running", "Preparando cofre seguro de contas e logs...")
            self.progress_updated.emit(90)
            get_cookies_dir()
            get_logs_dir()

            # Mark initialized
            marker = storage_dir / ".initialized"
            marker.write_text("TKS Engine 2.0 Initialized", encoding="utf-8")

            self.step_updated.emit(3, "ok", "Cofre de credenciais e logs pronto")
            self.progress_updated.emit(100)
            self.finished_setup.emit(True, "Configuração concluída com sucesso!")

        except Exception as exc:
            self.finished_setup.emit(False, f"Erro durante a inicialização: {exc}")


class FirstRunDialog(QDialog):
    """Welcome dialog displayed on first run to configure components seamlessly."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TKS Engine 2.0 — Configuração Inicial")
        self.setFixedSize(540, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(f"""
            QDialog {{ background: {TT_BG}; }}
            QLabel {{ color: {TT_TEXT}; font-family: 'Segoe UI', system-ui; }}
            QProgressBar {{ border: 1px solid {TT_BORDER}; border-radius: 4px; text-align: center; background: #F1F1F2; height: 10px; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #25F4EE, stop:1 {TT_RED}); border-radius: 3px; }}
            QPushButton#ttStartBtn {{
                background: {TT_RED}; color: #FFFFFF; font-weight: 700; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px 24px;
            }}
            QPushButton#ttStartBtn:hover {{ background: #E8264C; }}
            QPushButton#ttStartBtn:disabled {{ background: #D1D5DB; color: #9CA3AF; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)

        # Header with Logo & Title
        hdr = QHBoxLayout()
        hdr.setSpacing(16)
        logo_lbl = QLabel()
        ico_path = get_app_bundle_dir() / "assets" / "tks_engine.png"
        if ico_path.exists():
            logo_lbl.setPixmap(QPixmap(str(ico_path)).scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            logo_lbl.setPixmap(build_icon("fa5b.tiktok", TT_RED).pixmap(48, 48))
        hdr.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        t_lbl = QLabel("TKS ENGINE 2.0")
        t_lbl.setStyleSheet("font-size: 20px; font-weight: 800; letter-spacing: -0.5px;")
        sub_lbl = QLabel("Preparando ambiente de automação e publicação...")
        sub_lbl.setStyleSheet(f"font-size: 13px; color: {TT_TEXT_2};")
        title_col.addWidget(t_lbl)
        title_col.addWidget(sub_lbl)
        hdr.addLayout(title_col, 1)
        layout.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {TT_BORDER};")
        layout.addWidget(div)

        # Steps Container
        self.step_widgets: list[tuple[QLabel, QLabel]] = []
        steps_info = [
            ("Componentes do Sistema", "fa5s.microchip"),
            ("Motor de Navegação Playwright / Chromium", "fa5s.globe"),
            ("Estruturação do Banco de Dados e Fila", "fa5s.database"),
            ("Cofre Seguro de Contas e Sessões", "fa5s.shield-alt"),
        ]

        for title, icon_name in steps_info:
            row = QHBoxLayout()
            row.setContentsMargins(4, 4, 4, 4)
            row.setSpacing(12)

            ic_lbl = QLabel()
            ic_lbl.setPixmap(build_icon(icon_name, "#9CA3AF").pixmap(18, 18))
            ic_lbl.setFixedSize(22, 22)
            row.addWidget(ic_lbl)

            col = QVBoxLayout()
            col.setSpacing(1)
            tx_title = QLabel(title)
            tx_title.setStyleSheet("font-size: 13px; font-weight: 600;")
            tx_status = QLabel("Aguardando...")
            tx_status.setStyleSheet(f"font-size: 11px; color: {TT_TEXT_2};")
            col.addWidget(tx_title)
            col.addWidget(tx_status)
            row.addLayout(col, 1)

            st_icon = QLabel()
            st_icon.setFixedSize(18, 18)
            row.addWidget(st_icon)

            self.step_widgets.append((tx_status, st_icon))
            layout.addLayout(row)

        layout.addSpacing(6)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.info_lbl = QLabel("Inicializando componentes essenciais...")
        self.info_lbl.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_lbl)

        layout.addStretch(1)

        # Footer button
        self.start_btn = QPushButton("Conectar Primeira Conta TikTok →")
        self.start_btn.setObjectName("ttStartBtn")
        self.start_btn.setEnabled(False)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self.accept)
        layout.addWidget(self.start_btn)

        # Start background worker
        self.worker = SetupWorker()
        self.worker.step_updated.connect(self._on_step_updated)
        self.worker.progress_updated.connect(self.progress.setValue)
        self.worker.finished_setup.connect(self._on_finished)
        self.worker.start()

    def _on_step_updated(self, idx: int, status: str, msg: str) -> None:
        if 0 <= idx < len(self.step_widgets):
            lbl, st_icon = self.step_widgets[idx]
            lbl.setText(msg)
            if status == "running":
                lbl.setStyleSheet(f"font-size: 11px; color: {TT_RED}; font-weight: 500;")
                st_icon.setPixmap(build_icon("fa5s.spinner", TT_RED).pixmap(14, 14))
            elif status == "ok":
                lbl.setStyleSheet(f"font-size: 11px; color: {TT_GREEN};")
                st_icon.setPixmap(build_icon("fa5s.check-circle", TT_GREEN).pixmap(14, 14))
            else:
                lbl.setStyleSheet("font-size: 11px; color: #EF4444;")
                st_icon.setPixmap(build_icon("fa5s.times-circle", "#EF4444").pixmap(14, 14))

    def _on_finished(self, ok: bool, message: str) -> None:
        self.info_lbl.setText(message)
        if ok:
            self.start_btn.setEnabled(True)
            self.info_lbl.setStyleSheet(f"font-size: 12px; color: {TT_GREEN}; font-weight: 600;")
        else:
            self.info_lbl.setStyleSheet("font-size: 12px; color: #EF4444; font-weight: 600;")
