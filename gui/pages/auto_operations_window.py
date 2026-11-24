"""TKS Engine 3.0 — Interface Gráfica de Operações Automáticas (Auto Operations GUI).

Exibe os 6 personagens/departamentos como ilustrações visuais e opera 100% no piloto
automático: vigia E:\\ORLA1200\\1..6, alterna contas de acordo com os personagens,
aplica legenda automática, agenda no TikTok Studio e confirma a publicação.
"""
from __future__ import annotations

import asyncio
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.account_manager import AccountManager
from core.browser_runtime import BrowserRuntime
from core.db_manager import DatabaseManager
from core.execution_coordinator import ExecutionCoordinator
from core.local_folder_watcher import LocalFolderWatcher
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus, QueueManager
from core.round_robin_router import RoundRobinRouter
from gui.theme.manager import ThemeManager

# Mapeamento oficial dos 6 personagens e contas (100% Exclusivo TikTok)
CHARACTERS_MAP = [
    {
        "id": "employee-01",
        "dept_id": "dept_tiktok_01",
        "name": "Personagem 01",
        "role": "TikTok 01",
        "folder": "1",
        "drawer": "drawer-01",
        "account": "@unamyti",
        "emoji": "📱",
        "color": "#00F2FE",
    },
    {
        "id": "employee-02",
        "dept_id": "dept_tiktok_02",
        "name": "Personagem 02",
        "role": "TikTok 02",
        "folder": "2",
        "drawer": "drawer-02",
        "account": "@valueini",
        "emoji": "📱",
        "color": "#FE2C55",
    },
    {
        "id": "employee-03",
        "dept_id": "dept_tiktok_03",
        "name": "Personagem 03",
        "role": "TikTok 03",
        "folder": "3",
        "drawer": "drawer-03",
        "account": "@vinihack537",
        "emoji": "📱",
        "color": "#25F4EE",
    },
    {
        "id": "employee-04",
        "dept_id": "dept_tiktok_04",
        "name": "Personagem 04",
        "role": "TikTok 04",
        "folder": "4",
        "drawer": "drawer-04",
        "account": "@vinihack979",
        "emoji": "📱",
        "color": "#FF0050",
    },
    {
        "id": "employee-05",
        "dept_id": "dept_tiktok_05",
        "name": "Personagem 05",
        "role": "TikTok 05",
        "folder": "5",
        "drawer": "drawer-05",
        "account": "@vinihack120",
        "emoji": "📱",
        "color": "#00F2FE",
    },
    {
        "id": "employee-06",
        "dept_id": "dept_tiktok_06",
        "name": "Personagem 06",
        "role": "TikTok 06",
        "folder": "6",
        "drawer": "drawer-06",
        "account": "@viniciusferraz218",
        "emoji": "📱",
        "color": "#FE2C55",
    },
]


class CharacterIllustrationCard(QFrame):
    """Card ilustrativo de um personagem exibindo seu departamento, conta e status ao vivo."""

    def __init__(self, data: dict[str, str], on_click: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = data
        self.dept_id = data["dept_id"]
        self.account_username = data["account"]
        self.on_click = on_click

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(120)
        self.setStyleSheet("""
            CharacterIllustrationCard {
                background-color: #1A1D24;
                border: 1px solid #2D323F;
                border-radius: 10px;
            }
            CharacterIllustrationCard:hover {
                border: 1px solid #84CC16;
                background-color: #20242D;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header com emoji/ilustração e nome
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.lbl_emoji = QLabel(data["emoji"])
        self.lbl_emoji.setStyleSheet("font-size: 24px;")
        top_row.addWidget(self.lbl_emoji)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.lbl_name = QLabel(f"Mesa {data['folder']} — {data['role']}")
        self.lbl_name.setStyleSheet("font-size: 13px; font-weight: 800; color: #FFFFFF;")
        self.lbl_char = QLabel(f"Conta: {data['account']} • {data['drawer']}")
        self.lbl_char.setStyleSheet("font-size: 11px; color: #8F95A3;")
        title_box.addWidget(self.lbl_name)
        title_box.addWidget(self.lbl_char)
        top_row.addLayout(title_box)
        top_row.addStretch()

        # Botão/Badge de Calendário
        self.btn_cal_badge = QLabel("📅 Calendário")
        self.btn_cal_badge.setStyleSheet("""
            background-color: rgba(132, 204, 22, 0.15);
            color: #84CC16;
            font-size: 10px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid rgba(132, 204, 22, 0.3);
        """)
        top_row.addWidget(self.btn_cal_badge)

        # Estrela de sucesso (inicialmente oculta)
        self.lbl_star = QLabel("⭐")
        self.lbl_star.setStyleSheet("font-size: 18px;")
        self.lbl_star.setVisible(False)
        top_row.addWidget(self.lbl_star)

        layout.addLayout(top_row)

    def mousePressEvent(self, event) -> None:
        if self.on_click:
            self.on_click(self.account_username)
        super().mousePressEvent(event)

        # Info de Conta e Pasta
        info_row = QHBoxLayout()
        self.lbl_account = QLabel(f"Conta: {data['account']}")
        self.lbl_account.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {data['color']};")
        self.lbl_folder = QLabel(f"E:\\ORLA1200\\{data['folder']}")
        self.lbl_folder.setStyleSheet("font-size: 10px; color: #6C7282; font-family: Consolas;")
        info_row.addWidget(self.lbl_account)
        info_row.addStretch()
        info_row.addWidget(self.lbl_folder)
        layout.addLayout(info_row)

        # Barra de Status Atual
        self.lbl_status = QLabel("Aguardando novo vídeo...")
        self.lbl_status.setStyleSheet("""
            background-color: #12141A;
            color: #8F95A3;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid #232732;
        """)
        layout.addWidget(self.lbl_status)

    def set_status(self, text: str, state: str = "idle") -> None:
        """Atualiza visualmente o status da ilustração do personagem."""
        if state == "working":
            self.lbl_status.setText(f"⏳ {text}")
            self.lbl_status.setStyleSheet("""
                background-color: #1E2D4A;
                color: #64B5F6;
                font-size: 11px;
                font-weight: 700;
                padding: 6px 8px;
                border-radius: 6px;
                border: 1px solid #1976D2;
            """)
            self.lbl_star.setVisible(False)
        elif state == "success":
            self.lbl_status.setText(f"✅ {text}")
            self.lbl_status.setStyleSheet("""
                background-color: #1B382B;
                color: #81C784;
                font-size: 11px;
                font-weight: 700;
                padding: 6px 8px;
                border-radius: 6px;
                border: 1px solid #388E3C;
            """)
            self.lbl_star.setVisible(True)
        elif state == "failed":
            self.lbl_status.setText(f"❌ {text}")
            self.lbl_status.setStyleSheet("""
                background-color: #381E24;
                color: #E57373;
                font-size: 11px;
                font-weight: 700;
                padding: 6px 8px;
                border-radius: 6px;
                border: 1px solid #D32F2F;
            """)
        else:
            self.lbl_status.setText(text)
            self.lbl_status.setStyleSheet("""
                background-color: #12141A;
                color: #8F95A3;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 8px;
                border-radius: 6px;
                border: 1px solid #232732;
            """)


class AutoOperationsMainWindow(QMainWindow):
    """Janela principal de automação autônoma do TKS Engine 3.0."""

    log_signal = pyqtSignal(str)

    def __init__(self, theme_manager: ThemeManager | None = None) -> None:
        super().__init__()
        self.setWindowTitle("TKS Engine 3.0 — Automação de Pastas e Agendamento Contínuo")
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)

        # Core subsystems
        self.db = DatabaseManager.get_instance()
        self.account_mgr = AccountManager()
        self.queue_mgr = QueueManager(self.db)
        self.router = RoundRobinRouter(self.queue_mgr, self.account_mgr)
        self.bridge = OfficeEventBridge.get_instance()

        self.runtime: BrowserRuntime | None = None
        self.coordinator: ExecutionCoordinator | None = None
        self.watcher: LocalFolderWatcher | None = None

        self._character_cards: dict[str, CharacterIllustrationCard] = {}
        self._is_real_publishing = True

        self.log_signal.connect(self._append_log_message)

        self._build_ui()
        self._start_automation()

        # Timer periódico para atualizar tabelas e estatísticas
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_data)
        self.timer.start(2000)

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0E1015;
                color: #E2E8F0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QLabel {
                color: #E2E8F0;
            }
            QTableWidget {
                background-color: #16181F;
                color: #E2E8F0;
                border: 1px solid #2D323F;
                border-radius: 8px;
                gridline-color: #1F232D;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #1A1D26;
                color: #94A3B8;
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid #2D323F;
                padding: 6px 10px;
            }
            QPushButton {
                background-color: #1E222D;
                color: #E2E8F0;
                border: 1px solid #33394A;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #272C3A;
                border: 1px solid #434B60;
            }
            QPushButton#primaryAction {
                background-color: #FE2C55;
                color: #FFFFFF;
                border: none;
            }
            QPushButton#primaryAction:hover {
                background-color: #E0264B;
            }
            QTextEdit {
                background-color: #0A0C10;
                color: #68D391;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #242834;
                border-radius: 6px;
                padding: 6px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(14)

        # Header Superior
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("TKS ENGINE 3.0 — AUTOMAÇÃO DE PASTAS & AGENDAMENTO")
        title.setStyleSheet("font-size: 18px; font-weight: 900; color: #FFFFFF; letter-spacing: 0.5px;")
        subtitle = QLabel("Operação automática contínua em E:\\ORLA1200\\1..6 • Alternância de contas por personagem • Legenda e horários inteligentes")
        subtitle.setStyleSheet("font-size: 12px; color: #718096;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box)
        header_row.addStretch()

        # Badges de Modo
        self.badge_mode = QLabel("MODO REAL AUTORIZADO")
        self.badge_mode.setStyleSheet("""
            background-color: #381E24;
            color: #FE2C55;
            font-size: 11px;
            font-weight: 800;
            padding: 6px 14px;
            border-radius: 14px;
            border: 1px solid #FE2C55;
        """)
        header_row.addWidget(self.badge_mode)

        self.btn_calendar = QPushButton("📅 Calendário de Agendamentos")
        self.btn_calendar.setStyleSheet("""
            QPushButton {
                background-color: rgba(132, 204, 22, 0.2);
                color: #84CC16;
                font-weight: 800;
                font-size: 11px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #84CC16;
            }
            QPushButton:hover {
                background-color: #84CC16;
                color: #0F172A;
            }
        """)
        self.btn_calendar.clicked.connect(lambda: self._open_calendar("@unamyti"))
        header_row.addWidget(self.btn_calendar)

        self.btn_web_office = QPushButton("🌐 Abrir Escritório 3D")
        self.btn_web_office.clicked.connect(lambda: webbrowser.open("http://localhost:3005"))
        header_row.addWidget(self.btn_web_office)

        root_layout.addLayout(header_row)

        # Seção das 6 Ilustrações dos Personagens (Grid 3x2)
        grid_characters = QGridLayout()
        grid_characters.setSpacing(12)

        for i, char_data in enumerate(CHARACTERS_MAP):
            card = CharacterIllustrationCard(char_data, on_click=self._open_calendar)
            self._character_cards[char_data["dept_id"]] = card
            row = i // 3
            col = i % 3
            grid_characters.addWidget(card, row, col)

        root_layout.addLayout(grid_characters)

        # Tabela de Vídeos / Fila de Agendamento
        lbl_queue = QLabel("FILA DE PROCESSAMENTO & AGENDAMENTOS REAIS")
        lbl_queue.setStyleSheet("font-size: 13px; font-weight: 800; color: #CBD5E1; margin-top: 10px; margin-bottom: 2px;")
        root_layout.addWidget(lbl_queue)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Pasta",
            "Arquivo de Vídeo",
            "Mesa TikTok",
            "Entrada (Detectado)",
            "Data Programada (TikTok)",
            "Legenda",
            "Status",
            "Detalhes / Erro",
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(180)
        root_layout.addWidget(self.table)

        # Console de Logs ao Vivo
        lbl_console = QLabel("LOG OPERACIONAL EM TEMPO REAL")
        lbl_console.setStyleSheet("font-size: 12px; font-weight: 800; color: #94A3B8; margin-top: 6px;")
        root_layout.addWidget(lbl_console)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setFixedHeight(140)
        root_layout.addWidget(self.log_console)

        # Barra de Controles Inferior
        bottom_bar = QHBoxLayout()
        self.btn_rescan = QPushButton("🔄 Forçar Varredura de Pastas")
        self.btn_rescan.clicked.connect(self._force_rescan)
        bottom_bar.addWidget(self.btn_rescan)

        self.btn_clear_history = QPushButton("🧹 Limpar Histórico de Testes")
        self.btn_clear_history.clicked.connect(self._clear_old_history)
        bottom_bar.addWidget(self.btn_clear_history)

        self.btn_toggle_mode = QPushButton("Alternar para Homologação (Simulado)")
        self.btn_toggle_mode.clicked.connect(self._toggle_publishing_mode)
        bottom_bar.addWidget(self.btn_toggle_mode)

        bottom_bar.addStretch()

        self.lbl_stats = QLabel("Concorrência: 0 / 2 | Agendamentos Confirmados: 0")
        self.lbl_stats.setStyleSheet("font-size: 12px; font-weight: 700; color: #CBD5E1;")
        bottom_bar.addWidget(self.lbl_stats)

        root_layout.addLayout(bottom_bar)

    def _start_automation(self) -> None:
        """Inicializa os subsistemas e ativa o monitoramento em segundo plano."""
        self._append_log_message("Iniciando TKS Engine 3.0 em modo automático...")

        # Conectar eventos do bridge para atualizar os cards dos personagens
        def bridge_listener(event: dict[str, Any]) -> None:
            dept_id = event.get("department_id")
            event_name = event.get("event")
            status = event.get("status")

            if dept_id and dept_id in self._character_cards:
                card = self._character_cards[dept_id]
                if event_name in ("video.upload_started", "account.execution_started"):
                    card.set_status("Levantando da mesa / Upload em andamento...", "working")
                elif event_name in ("video.scheduled", "task.completed"):
                    card.set_status("Vídeo agendado no TikTok Studio! ⭐", "success")
                elif event_name == "video.failed":
                    card.set_status(f"Falha: {event.get('extra', {}).get('error', 'Erro')}", "failed")

            # Atualizar log
            msg = f"[{datetime.now().strftime('%H:%M:%S')}] {event_name}: {status or ''} ({dept_id or ''})"
            self.log_signal.emit(msg)

        self.bridge.subscribe(bridge_listener)

        # Iniciar Watcher local em E:\ORLA1200
        try:
            self.watcher = LocalFolderWatcher(
                base_dir=Path(r"E:\ORLA1200"),
                db_manager=self.db,
                queue_manager=self.queue_mgr,
                bridge=self.bridge,
            )
            self.watcher.start()
            self._append_log_message("LocalFolderWatcher ativo monitorando pastas E:\\ORLA1200\\1..6 continuamente.")
        except Exception as e:
            self._append_log_message(f"Erro ao iniciar LocalFolderWatcher: {e}")

        # Iniciar BrowserRuntime e ExecutionCoordinator assincronamente
        QTimer.singleShot(500, self._init_coordinator_async)

    def _init_coordinator_async(self) -> None:
        """Inicializa o BrowserRuntime e o ExecutionCoordinator."""
        import threading

        def run_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.runtime = BrowserRuntime()
            loop.run_until_complete(self.runtime.start(headless=True))

            self.coordinator = ExecutionCoordinator(
                browser_runtime=self.runtime,
                queue_manager=self.queue_mgr,
                account_manager=self.account_mgr,
                router=self.router,
                db_manager=self.db,
                max_concurrent_jobs=2,
                max_jobs_per_account=1,
                allow_real_publishing=self._is_real_publishing,
            )
            self.coordinator.set_real_publishing(self._is_real_publishing, confirmed=True)
            self.coordinator.start()

            # Hook para mover arquivo para _PROCESSADOS quando SCHEDULED ou PUBLISHED
            def on_coord_event(ev: str, data: dict[str, Any]) -> None:
                if ev == "job.completed":
                    jid = data.get("job_id")
                    st = data.get("status")
                    if jid and st in (JobStatus.SCHEDULED, JobStatus.SCHEDULED.value, "SCHEDULED", JobStatus.PUBLISHED, JobStatus.PUBLISHED.value, "PUBLISHED") and self.watcher:
                        self.watcher.archive_processed_video(jid)

            self.coordinator.register_callback(on_coord_event)
            self.log_signal.emit("ExecutionCoordinator ativo com concorrência máxima de 2 contas.")

            # Loop infinito do coordinator
            async def worker_loop() -> None:
                while True:
                    try:
                        if self.coordinator and not self.coordinator.is_paused and not self.coordinator.is_stopped:
                            dry_run = not self.coordinator.allow_real_publishing
                            spawned = await self.coordinator.step(dry_run=dry_run)
                            if spawned > 0:
                                self.log_signal.emit(f"Iniciando processamento para {spawned} conta(s) no TikTok Studio...")
                    except Exception as exc:
                        self.log_signal.emit(f"Erro no loop do coordinator: {exc}")
                    await asyncio.sleep(2.5)

            loop.run_until_complete(worker_loop())

        t = threading.Thread(target=run_loop, daemon=True)
        t.start()

    def _open_calendar(self, account: str = "@unamyti") -> None:
        """Abre o diálogo do calendário de agendamentos para a conta/mesa selecionada."""
        try:
            from gui.pages.employee_calendar_dialog import EmployeeCalendarDialog
            dlg = EmployeeCalendarDialog(initial_account=account, db=self.db, parent=self)
            dlg.exec()
        except Exception as exc:
            self._append_log_message(f"Erro ao abrir calendário de agendamentos: {exc}")

    def _force_rescan(self) -> None:
        """Dispara varredura forçada nas pastas."""
        self._append_log_message("Varredura manual disparada nas pastas E:\\ORLA1200\\1..6...")
        if self.watcher:
            import threading
            threading.Thread(target=self.watcher.scan_now, daemon=True).start()

    def _toggle_publishing_mode(self) -> None:
        """Alterna entre Modo Real e Homologação."""
        self._is_real_publishing = not self._is_real_publishing
        if self.coordinator:
            self.coordinator.set_real_publishing(self._is_real_publishing, confirmed=True)

        if self._is_real_publishing:
            self.badge_mode.setText("MODO REAL AUTORIZADO")
            self.badge_mode.setStyleSheet("""
                background-color: #381E24;
                color: #FE2C55;
                font-size: 11px;
                font-weight: 800;
                padding: 6px 14px;
                border-radius: 14px;
                border: 1px solid #FE2C55;
            """)
            self.btn_toggle_mode.setText("Alternar para Homologação (Simulado)")
            self._append_log_message("Modo Real ATIVADO: Publicações serão agendadas oficialmente no TikTok Studio.")
        else:
            self.badge_mode.setText("MODO HOMOLOGAÇÃO (SIMULAÇÃO)")
            self.badge_mode.setStyleSheet("""
                background-color: #1E2D4A;
                color: #64B5F6;
                font-size: 11px;
                font-weight: 800;
                padding: 6px 14px;
                border-radius: 14px;
                border: 1px solid #1976D2;
            """)
            self.btn_toggle_mode.setText("Alternar para Modo Real (Oficial)")
            self._append_log_message("Modo Homologação ATIVADO: Playwright preencherá o formulário sem clicar em Agendar.")

    def _clear_old_history(self) -> None:
        """Limpa registros de testes antigos (FAILED, SUPERSEDED, UNKNOWN) e re-escaneia as pastas."""
        try:
            with self.db.get_connection() as conn:
                cur = conn.execute("DELETE FROM jobs WHERE status IN ('SUPERSEDED', 'FAILED', 'UNKNOWN')")
                conn.commit()
                deleted = cur.rowcount
            self._append_log_message(f"🧹 Histórico antigo limpo ({deleted} registros de teste removidos).")
            if self.watcher:
                self.watcher.scan_all_folders()
            self._refresh_data()
        except Exception as e:
            self._append_log_message(f"Erro ao limpar histórico: {e}")

    def _format_relative_time(self, raw_dt: str) -> str:
        """Formata data/hora para indicar claramente 'Hoje às HH:MM' ou 'Ontem às HH:MM'."""
        if not raw_dt:
            return "-"
        try:
            from datetime import timedelta
            cleaned = raw_dt.replace("T", " ").split(".")[0]
            dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
            today = datetime.now().date()
            if dt.date() == today:
                return f"Hoje às {dt.strftime('%H:%M:%S')}"
            elif dt.date() == (today - timedelta(days=1)):
                return f"Ontem às {dt.strftime('%H:%M')}"
            else:
                return dt.strftime("%d/%m %H:%M")
        except Exception:
            return raw_dt

    def _refresh_data(self) -> None:
        """Atualiza a tabela de tarefas e estatísticas do banco de dados."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, filename, department_id, account_id, caption, schedule_time, status, created_at, error_message
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT 30
                """)
                rows = cursor.fetchall()

                self.table.setRowCount(len(rows))
                scheduled_count = 0

                for r_idx, row in enumerate(rows):
                    fname = str(row["filename"] or "")
                    dept_id = str(row["department_id"] or "")
                    acc_id = str(row["account_id"] or "")
                    caption = str(row["caption"] or "meu brasil #fy #foryou")
                    sched_time = str(row["schedule_time"] or "")
                    status = str(row["status"] or "")
                    created_at = str(row["created_at"] or "")
                    err_msg = str(row["error_message"] or "")

                    if status == "SCHEDULED":
                        scheduled_count += 1

                    # Mapear pasta e conta TikTok (com suporte retroativo)
                    legacy_dept_map = {
                        "dept_instagram": "dept_tiktok_01",
                        "dept_mercadolivre": "dept_tiktok_02",
                        "dept_shorts": "dept_tiktok_03",
                        "dept_tiktok": "dept_tiktok_04",
                        "dept_tiktokshop": "dept_tiktok_05",
                        "dept_youtube": "dept_tiktok_06",
                    }
                    normalized_dept = legacy_dept_map.get(dept_id, dept_id)
                    char_info = next((c for c in CHARACTERS_MAP if c["dept_id"] == normalized_dept), None)
                    folder_str = char_info["folder"] if char_info else "-"
                    char_name = char_info["role"] if char_info else dept_id
                    acc_str = char_info["account"] if char_info else acc_id
                    emoji = char_info["emoji"] if char_info else "📱"

                    created_str = self._format_relative_time(created_at)

                    self.table.setItem(r_idx, 0, QTableWidgetItem(f"Pasta {folder_str}"))
                    self.table.setItem(r_idx, 1, QTableWidgetItem(fname))
                    self.table.setItem(r_idx, 2, QTableWidgetItem(f"{emoji} {char_name} ({acc_str})"))
                    
                    # Horário de entrada claro (Hoje/Ontem)
                    self.table.setItem(r_idx, 3, QTableWidgetItem(created_str))
                    
                    # Data programada no TikTok
                    self.table.setItem(r_idx, 4, QTableWidgetItem(sched_time))
                    self.table.setItem(r_idx, 5, QTableWidgetItem(caption))

                    st_item = QTableWidgetItem(status)
                    if status == "SCHEDULED":
                        st_item.setForeground(QColor("#81C784"))
                    elif status in ("RUNNING", "UPLOADING", "PROCESSING", "SUBMITTING"):
                        st_item.setForeground(QColor("#64B5F6"))
                    elif status == "FAILED":
                        st_item.setForeground(QColor("#E57373"))
                    elif status == "SUPERSEDED":
                        st_item.setForeground(QColor("#9E9E9E"))
                    self.table.setItem(r_idx, 6, st_item)

                    # Detalhes / Erro
                    detail_text = err_msg if err_msg else ("Agendamento Confirmado ✅" if status == "SCHEDULED" else "")
                    self.table.setItem(r_idx, 7, QTableWidgetItem(detail_text))

                active_count = len([r for r in rows if r["status"] in ("RUNNING", "UPLOADING", "PROCESSING", "SUBMITTING")])
                self.lbl_stats.setText(f"Concorrência: {active_count} / 2 | Agendamentos Confirmados: {scheduled_count}")

        except Exception as e:
            pass

    def _append_log_message(self, text: str) -> None:
        """Adiciona mensagem no console de logs com auto-scroll."""
        self.log_console.append(text)
        self.log_console.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event: Any) -> None:
        """Encerra graciosamente o runtime e watcher."""
        if self.watcher:
            self.watcher.stop()
        if self.coordinator:
            self.coordinator.stop()
        event.accept()
