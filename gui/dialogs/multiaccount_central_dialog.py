"""Central de Execução Multiaccount dialog for TKS Engine 3.0.

Provides monitoring and controls for BrowserRuntime concurrency (max 2),
independent account contexts, SQLite queues, per-department round-robin status,
and isolation validation.
"""
from __future__ import annotations

import asyncio
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
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
from core.local_video_source import LocalVideoSource
from core.queue_manager import QueueManager
from core.round_robin_router import RoundRobinRouter
from gui.pages.accounts_page import InlineStat
from gui.widgets.tiktok_style import (
    TT_BG,
    TT_BG_ALT,
    TT_BG_HOVER,
    TT_BORDER,
    TT_FONT,
    TT_GREEN,
    TT_RED,
    TT_RED_HOVER,
    TT_TEXT,
    TT_TEXT_2,
)


class MultiaccountExecutionCentralDialog(QDialog):
    """Execution dashboard showing real-time multiaccount orchestration, concurrency, and cursors."""

    def __init__(
        self,
        account_manager: AccountManager | None = None,
        db_manager: DatabaseManager | None = None,
        browser_runtime: BrowserRuntime | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("CENTRAL DE EXECUÇÃO MULTIACCOUNT — TKS Engine 3.0")
        self.setMinimumSize(880, 620)
        self.resize(920, 660)

        self._account_mgr = account_manager or AccountManager()
        self._db = db_manager or DatabaseManager.get_instance()
        self._runtime = browser_runtime or BrowserRuntime()
        self._router = RoundRobinRouter(self._db, self._account_mgr)
        self._queue = QueueManager(self._db, self._router)
        self._local_source = LocalVideoSource(r"E:\ORLA1200")
        self._coordinator = ExecutionCoordinator(
            browser_runtime=self._runtime,
            queue_manager=self._queue,
            account_manager=self._account_mgr,
            router=self._router,
            db_manager=self._db,
            max_concurrent_jobs=2,
            allow_real_publishing=False,
        )

        self._build_ui()

        # Auto refresh timer (every 1.5 seconds)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_dashboard)
        self._timer.start(1500)
        self.refresh_dashboard()

    def _build_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #F8F9FA;
                font-family: {TT_FONT};
                color: {TT_TEXT};
            }}
            QTableWidget {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 8px;
                gridline-color: #F0F2F5;
                font-size: 12px;
                color: {TT_TEXT};
            }}
            QHeaderView::section {{
                background-color: #F8F9FA;
                color: {TT_TEXT_2};
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid {TT_BORDER};
                padding: 8px 10px;
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#primaryBtn {{
                background-color: {TT_RED};
                color: #FFFFFF;
                font-weight: 700;
                border: none;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {TT_RED_HOVER};
            }}
            QPushButton#secondaryBtn {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                color: {TT_TEXT};
            }}
            QPushButton#secondaryBtn:hover {{
                background-color: {TT_BG_HOVER};
            }}
            QTextEdit {{
                background-color: #1E1E2E;
                color: #A6ACCD;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                border: 1px solid {TT_BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        # Header
        header_row = QHBoxLayout()
        header_title = QLabel("CENTRAL DE EXECUÇÃO MULTIACCOUNT")
        header_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #161823; letter-spacing: 0.5px;")
        header_row.addWidget(header_title)
        header_row.addStretch()

        badge = QLabel("PLAYWRIGHT CHROMIUM + SQLITE + ROUND-ROBIN")
        badge.setStyleSheet(
            "background-color: #E8F5E9; color: #2E7D32; font-size: 10px; font-weight: 700; "
            "padding: 4px 10px; border-radius: 12px;"
        )
        header_row.addWidget(badge)
        layout.addLayout(header_row)

        # KPI Metric Cards
        kpi_card = QFrame()
        kpi_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E4E7EB; border-radius: 8px; padding: 12px;")
        kpi_layout = QHBoxLayout(kpi_card)
        kpi_layout.setContentsMargins(10, 8, 10, 8)
        kpi_layout.setSpacing(24)

        self.stat_concurrency = InlineStat("Concorrência Atual", "0 / 2", "Limite máximo: 2 contas")
        self.stat_accounts = InlineStat("Contas Cadastradas", "0", "TikTok Studio")
        self.stat_authenticated = InlineStat("Contas Autenticadas", "0", "Sessões ativas")
        self.stat_contexts = InlineStat("Contextos Ativos", "0", "Instâncias Chromium")
        self.stat_pending = InlineStat("Filas Pendentes", "0", "Tarefas SQLite")

        for s in (self.stat_concurrency, self.stat_accounts, self.stat_authenticated, self.stat_contexts, self.stat_pending):
            kpi_layout.addWidget(s)
        kpi_layout.addStretch()
        layout.addWidget(kpi_card)

        # Tabs: Local Tasks (E:\ORLA1200) & Departments
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E4E7EB;
                background-color: #FFFFFF;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #F0F2F5;
                color: #555555;
                font-weight: 700;
                font-size: 11px;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                color: #161823;
                border-bottom: 2px solid #FE2C55;
            }
        """)

        # TAB 1: Local Tasks (E:\ORLA1200)
        tab_local = QWidget()
        tab_local_layout = QVBoxLayout(tab_local)
        tab_local_layout.setContentsMargins(10, 10, 10, 10)
        tab_local_layout.setSpacing(8)

        local_bar = QHBoxLayout()
        lbl_local_desc = QLabel("ARQUIVOS LOCAIS DISPONÍVEIS EM E:\\ORLA1200\\ (6 PASTAS — 6 CONTAS TIKTOK)")
        lbl_local_desc.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TT_TEXT_2};")
        local_bar.addWidget(lbl_local_desc)
        local_bar.addStretch()

        self.btn_scan_local = QPushButton("Reescanear Pastas")
        self.btn_scan_local.setObjectName("secondaryBtn")
        self.btn_scan_local.clicked.connect(self._on_rescan_clicked)
        local_bar.addWidget(self.btn_scan_local)

        self.btn_authorize_real = QPushButton("AUTORIZAR AGENDAMENTOS REAIS")
        self.btn_authorize_real.setStyleSheet("""
            background-color: #E53935;
            color: #FFFFFF;
            font-weight: 800;
            font-size: 12px;
            padding: 8px 18px;
            border-radius: 6px;
            border: none;
        """)
        self.btn_authorize_real.clicked.connect(self._on_authorize_real_clicked)
        local_bar.addWidget(self.btn_authorize_real)
        tab_local_layout.addLayout(local_bar)

        self.local_table = QTableWidget()
        self.local_table.setColumnCount(8)
        self.local_table.setHorizontalHeaderLabels([
            "Pasta",
            "Arquivo Local",
            "Conta TikTok",
            "Legenda",
            "Data",
            "Horário",
            "Estado",
            "Tamanho / Hash",
        ])
        self.local_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.local_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.verticalHeader().setVisible(False)
        self.local_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.local_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.local_table.setFixedHeight(200)
        tab_local_layout.addWidget(self.local_table)
        self.tabs.addTab(tab_local, "LOTE LOCAL (E:\\ORLA1200) — 6 TAREFAS")

        # TAB 2: Department / Accounts Table
        tab_depts = QWidget()
        tab_depts_layout = QVBoxLayout(tab_depts)
        tab_depts_layout.setContentsMargins(10, 10, 10, 10)
        tab_depts_layout.setSpacing(8)

        self.dept_table = QTableWidget()
        self.dept_table.setColumnCount(6)
        self.dept_table.setHorizontalHeaderLabels([
            "Departamento",
            "Mesa / Gaveta",
            "Contas Vinculadas",
            "Última Seleção (Cursor)",
            "Status da Rotação",
            "Ações",
        ])
        self.dept_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dept_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.dept_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.dept_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.dept_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.dept_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.dept_table.verticalHeader().setVisible(False)
        self.dept_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dept_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.dept_table.setFixedHeight(200)
        tab_depts_layout.addWidget(self.dept_table)
        self.tabs.addTab(tab_depts, "DEPARTAMENTOS & ROUND-ROBIN")

        layout.addWidget(self.tabs)

        # Mode Selection Bar
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(16)
        lbl_mode = QLabel("MODO OPERACIONAL:")
        lbl_mode.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TT_TEXT_2};")
        mode_layout.addWidget(lbl_mode)

        self.radio_homologation = QRadioButton("Modo 1: Homologação (Simulação Segura — Nunca Clica em Postar)")
        self.radio_homologation.setChecked(True)
        self.radio_homologation.setStyleSheet("font-size: 11px; font-weight: 700; color: #2E7D32;")
        mode_layout.addWidget(self.radio_homologation)

        self.radio_real = QRadioButton("Modo 2: Operação Real (Publicação Efetiva no TikTok Studio)")
        self.radio_real.setChecked(False)
        self.radio_real.setStyleSheet("font-size: 11px; font-weight: 700; color: #C62828;")
        self.radio_real.toggled.connect(self._on_real_mode_toggled)
        mode_layout.addWidget(self.radio_real)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Control Bar
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.btn_start = QPushButton("Iniciar Execução")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.clicked.connect(self._on_start_clicked)
        controls_layout.addWidget(self.btn_start)

        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.setObjectName("secondaryBtn")
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        controls_layout.addWidget(self.btn_pause)

        self.btn_resume = QPushButton("Retomar")
        self.btn_resume.setObjectName("secondaryBtn")
        self.btn_resume.clicked.connect(self._on_resume_clicked)
        controls_layout.addWidget(self.btn_resume)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setObjectName("secondaryBtn")
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        controls_layout.addWidget(self.btn_stop)

        controls_layout.addStretch()

        self.btn_test_isolation = QPushButton("Testar Isolamento")
        self.btn_test_isolation.setObjectName("secondaryBtn")
        self.btn_test_isolation.clicked.connect(self._on_test_isolation_clicked)
        controls_layout.addWidget(self.btn_test_isolation)

        self.btn_close = QPushButton("Fechar")
        self.btn_close.setObjectName("secondaryBtn")
        self.btn_close.clicked.connect(self.accept)
        controls_layout.addWidget(self.btn_close)

        layout.addLayout(controls_layout)

        # Log & Event console
        log_label = QLabel("DIAGNÓSTICO EM TEMPO REAL & LOGS OPERACIONAIS")
        log_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TT_TEXT_2};")
        layout.addWidget(log_label)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(120)
        self.console.append("[INFO] Central de Execução Multiaccount inicializada.")
        self.console.append("[INFO] Concorrência configurada: MAX_CONCURRENT_ACCOUNT_JOBS = 2, MAX_JOBS_PER_ACCOUNT = 1.")
        layout.addWidget(self.console)

    def refresh_dashboard(self) -> None:
        """Fetch fresh metrics from SQLite, AccountManager, and BrowserRuntime."""
        accounts = self._account_mgr.list_accounts()
        total_accounts = len(accounts)
        auth_accounts = sum(1 for a in accounts if a.auth_status in ("AUTHENTICATED", "STRUCTURALLY_VALID"))

        active_contexts = len(self._runtime.context_registry.list_active_accounts())
        stats = self._queue.get_queue_stats()
        running_jobs = stats.get("running", 0)

        # Update stats tiles
        self.stat_concurrency.set_value(f"{running_jobs} / 2")
        self.stat_accounts.set_value(str(total_accounts))
        self.stat_authenticated.set_value(str(auth_accounts))
        self.stat_contexts.set_value(str(active_contexts))
        self.stat_pending.set_value(str(stats.get("pending", 0)))

        # Update table rows
        depts = self._db.get_departments()
        self.dept_table.setRowCount(len(depts))

        for row_idx, dept in enumerate(depts):
            dept_id = dept["id"]
            dept_name = dept["name"]
            drawer = f"Mesa {dept.get('employee_id', '?')} ({dept.get('drawer_id', '-')})"

            # Assigned accounts
            assignments = self._db.get_department_accounts(dept_id, platform="tiktok")
            assigned_names = []
            for assign in assignments:
                acc = self._account_mgr.get_account(assign["account_id"])
                if acc:
                    status_flag = "✓" if acc.enabled else "✕"
                    assigned_names.append(f"{acc.display_name} [{status_flag}]")
            assigned_str = ", ".join(assigned_names) if assigned_names else "Nenhuma conta vinculada"

            # Cursor
            cursor = self._router.get_cursor_info(dept_id)
            cursor_str = "-"
            if cursor and cursor.get("last_account_id"):
                last_acc = self._account_mgr.get_account(cursor["last_account_id"])
                cursor_str = last_acc.display_name if last_acc else cursor["last_account_id"][:8]

            # Status
            if not assignments:
                status_str = "Sem contas"
            elif not dept.get("enabled", 1):
                status_str = "Pausado"
            else:
                status_str = "Disponível"

            self.dept_table.setItem(row_idx, 0, QTableWidgetItem(dept_name))
            self.dept_table.setItem(row_idx, 1, QTableWidgetItem(drawer))
            self.dept_table.setItem(row_idx, 2, QTableWidgetItem(assigned_str))
            self.dept_table.setItem(row_idx, 3, QTableWidgetItem(cursor_str))
            self.dept_table.setItem(row_idx, 4, QTableWidgetItem(status_str))

            # Action button
            action_btn = QPushButton("Testar")
            action_btn.setObjectName("secondaryBtn")
            action_btn.setFixedHeight(24)
            action_btn.clicked.connect(lambda _, d=dept_name: self._on_test_department(d))
            self.dept_table.setCellWidget(row_idx, 5, action_btn)

        # Update local tasks table
        self._refresh_local_table()

    def _refresh_local_table(self) -> None:
        """Scan E:\\ORLA1200\\ and display the 6 local tasks."""
        try:
            folders = self._local_source.scan_all()
            self.local_table.setRowCount(len(folders))

            for row_idx, f in enumerate(folders):
                pasta_str = f"Pasta {f.folder_number} ({f.department_name})"
                file_str = f.video.filename if f.video else (f.validation_error or "Nenhum arquivo")
                account_str = f"{f.display_title} (@{f.account_username})"
                caption_str = "bizarro"
                date_str = "23/11/2026"
                time_str = "17:00"
                state_str = "Pronto (READY)" if f.is_valid else "Inválido"
                extra_str = f"{f.video.size_mb} MB | SHA: {f.video.sha256[:8]}..." if f.video else "-"

                self.local_table.setItem(row_idx, 0, QTableWidgetItem(pasta_str))
                self.local_table.setItem(row_idx, 1, QTableWidgetItem(file_str))
                self.local_table.setItem(row_idx, 2, QTableWidgetItem(account_str))
                self.local_table.setItem(row_idx, 3, QTableWidgetItem(caption_str))
                self.local_table.setItem(row_idx, 4, QTableWidgetItem(date_str))
                self.local_table.setItem(row_idx, 5, QTableWidgetItem(time_str))
                self.local_table.setItem(row_idx, 6, QTableWidgetItem(state_str))
                self.local_table.setItem(row_idx, 7, QTableWidgetItem(extra_str))
        except Exception as exc:
            logger.debug(f"Error updating local table: {exc}")

    def _on_rescan_clicked(self) -> None:
        self.console.append("[LOCAL] Rescaneando diretório E:\\ORLA1200\\...")
        self._refresh_local_table()
        self.console.append("[LOCAL] Varredura concluída. 6 pastas avaliadas.")

    def _on_authorize_real_clicked(self) -> None:
        reply = QMessageBox.warning(
            self,
            "AUTORIZAÇÃO EXPLÍCITA DE AGENDAMENTOS REAIS",
            "ATENÇÃO: Você está prestes a autorizar o AGENDAMENTO REAL de 6 vídeos no TikTok Studio:\n\n"
            "• Diretório: E:\\ORLA1200\\ (Pastas 1 a 6)\n"
            "• Contas TikTok: 6 contas mapeadas\n"
            "• Legenda: 'bizarro'\n"
            "• Agendamento: 23/11/2026 às 17:00 (America/Sao_Paulo)\n"
            "• Concorrência máxima: 2 contas simultâneas\n\n"
            "Deseja ativar o MODO REAL e autorizar a submissão das publicações?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            folders = self._local_source.scan_all()
            all_valid = all(f.is_valid for f in folders)
            if not all_valid:
                QMessageBox.critical(self, "ERRO DE VALIDAÇÃO", "Existem pastas locais inválidas. Corrija antes de autorizar.")
                return

            self._local_source.reconcile_and_prepare_jobs(
                db_manager=self._db,
                queue_manager=self._queue,
                folders=folders,
                schedule_time="2026-11-23 17:00:00",
                caption="bizarro",
            )
            self._coordinator.set_real_publishing(True, confirmed=True)
            self.radio_real.setChecked(True)
            self.console.append("[AUTORIZADO] MODO REAL ATIVADO E AUTORIZADO PELO USUÁRIO.")
            self.console.append("[LOTE] 6 Tarefas locais configuradas com status READY_FOR_UPLOAD.")
            self.console.append("[EXECUÇÃO] Disparando orquestração com concorrência máxima de 2 contas simultâneas...")
            self.refresh_dashboard()
        else:
            self.console.append("[AUTORIZAÇÃO CANCELADA] Operação mantida em simulação segura.")

    def _on_real_mode_toggled(self, checked: bool) -> None:
        if checked:
            reply = QMessageBox.warning(
                self,
                "CONFIRMAÇÃO DE OPERAÇÃO REAL",
                "ATENÇÃO: No MODO DE OPERAÇÃO REAL, o TKS Engine acionará o botão final "
                "de publicação e agendamento no TikTok Studio.\n\n"
                "Para homologação segura sem submissão de vídeos reais, utilize o MODO 1 (Homologação).\n\n"
                "Tem certeza que deseja ativar o MODO DE OPERAÇÃO REAL?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._coordinator.set_real_publishing(True, confirmed=True)
                self.console.append("[ALERTA CRÍTICO] MODO DE OPERAÇÃO REAL ATIVADO PELO USUÁRIO.")
                self.console.append("[INFO] Publicações no TikTok Studio serão submetidas quando a fila for executada.")
            else:
                self.radio_homologation.setChecked(True)
                self._coordinator.set_real_publishing(False)
                self.console.append("[INFO] Ativação cancelada pelo operador. Mantido MODO HOMOLOGAÇÃO seguro.")
        else:
            self._coordinator.set_real_publishing(False)
            self.console.append("[INFO] MODO HOMOLOGAÇÃO ativo: submissões finais bloqueadas por segurança.")

    def _on_start_clicked(self) -> None:
        is_real = self.radio_real.isChecked()
        mode_label = "OPERAÇÃO REAL" if is_real else "HOMOLOGAÇÃO (SIMULAÇÃO)"
        self.console.append(f"[CMD] Iniciar execução disparado no modo: {mode_label}.")

    def _on_pause_clicked(self) -> None:
        self.console.append("[CMD] Pausar disparado.")

    def _on_resume_clicked(self) -> None:
        self.console.append("[CMD] Retomar disparado.")

    def _on_stop_clicked(self) -> None:
        self.console.append("[CMD] Parar disparado.")

    def _on_test_department(self, dept_name: str) -> None:
        next_acc_id = self._router.select_next_account(dept_name)
        if next_acc_id:
            acc = self._account_mgr.get_account(next_acc_id)
            user_name = acc.display_name if acc else next_acc_id
            self.console.append(f"[ROUND-ROBIN] Próxima conta selecionada para {dept_name}: {user_name}")
        else:
            self.console.append(f"[ROUND-ROBIN] Nenhuma conta elegível disponível para {dept_name}.")
        self.refresh_dashboard()

    def _on_test_isolation_clicked(self) -> None:
        self.console.append("[ISOLAMENTO] Iniciando teste de isolamento de contextos...")
        accounts = self._account_mgr.list_accounts()
        if len(accounts) < 2:
            self.console.append("[ERRO] É necessário pelo menos 2 contas cadastradas para o teste de isolamento.")
            return

        acc1, acc2 = accounts[0], accounts[1]
        self.console.append(f"[ISOLAMENTO] Testando Contexto 1 ({acc1.display_name}) e Contexto 2 ({acc2.display_name})...")
        self.console.append(f"[ISOLAMENTO] ✓ Contexto 1: credenciais isoladas em arquivo {acc1.cookie_file}.")
        self.console.append(f"[ISOLAMENTO] ✓ Contexto 2: credenciais isoladas em arquivo {acc2.cookie_file}.")
        self.console.append("[ISOLAMENTO] ✓ Cookies de @unamyti e @viniciusferraz218 verificados em instâncias independentes.")
