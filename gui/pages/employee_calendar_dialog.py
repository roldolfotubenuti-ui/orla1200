"""Employee Calendar Dialog for TKS Engine 3.0.

Exibe o calendário visual de agendamentos por computador/mesa do funcionário.
Inspirado no design minimalista com realce contínuo em verde limão/esmeralda.
"""
from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont, QCursor
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGridLayout,
    QScrollArea,
    QWidget,
)

from core.db_manager import DatabaseManager


class DayCellWidget(QFrame):
    """Célula individual de um dia no calendário."""

    def __init__(
        self,
        day_num: int,
        date_str: str,
        videos: list[dict[str, Any]],
        is_current_month: bool,
        is_selected: bool,
        on_click: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.date_str = date_str
        self.videos = videos
        self.on_click = on_click
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor) if is_current_month else QCursor(Qt.CursorShape.ArrowCursor))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        count = len(videos)
        has_videos = count > 0

        lbl_day = QLabel(str(day_num))
        lbl_day.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if not is_current_month:
            lbl_day.setStyleSheet("color: #4A4E5A; font-size: 11px;")
            self.setStyleSheet("background: transparent; border: none;")
        elif has_videos:
            # Destaque estilo pill verde limão (#84CC16) conforme referência
            lbl_day.setStyleSheet("color: #0F172A; font-weight: 900; font-size: 12px;")
            border_style = "border: 2px solid #FFFFFF;" if is_selected else "border: none;"
            self.setStyleSheet(f"""
                DayCellWidget {{
                    background-color: #84CC16;
                    border-radius: 8px;
                    {border_style}
                }}
                DayCellWidget:hover {{
                    background-color: #A3E635;
                }}
            """)
            lbl_count = QLabel(f"{count}/5")
            lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_count.setStyleSheet("color: #0F172A; font-size: 9px; font-weight: 800; background: rgba(0,0,0,0.15); border-radius: 4px; padding: 0 2px;")
            layout.addWidget(lbl_day)
            layout.addWidget(lbl_count)
            return
        else:
            border_style = "border: 1px solid #60A5FA; background-color: #1E293B;" if is_selected else "border: none; background: transparent;"
            lbl_day.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 600;")
            self.setStyleSheet(f"""
                DayCellWidget {{
                    border-radius: 8px;
                    {border_style}
                }}
                DayCellWidget:hover {{
                    background-color: #1E222D;
                }}
            """)

        layout.addWidget(lbl_day)

    def mousePressEvent(self, event) -> None:
        if self.date_str and self.on_click:
            self.on_click(self.date_str)
        super().mousePressEvent(event)


class EmployeeCalendarDialog(QDialog):
    """Diálogo completo de calendário por mesa/conta."""

    MONTH_NAMES = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    WEEKDAY_HEADERS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]

    DESK_LIST = [
        {"folder": "1", "dept": "dept_instagram", "account": "@unamyti", "name": "Mesa 1 — Instagram"},
        {"folder": "2", "dept": "dept_mercadolivre", "account": "@valueini", "name": "Mesa 2 — Mercado Livre"},
        {"folder": "3", "dept": "dept_shorts", "account": "@vinihack537", "name": "Mesa 3 — Shorts"},
        {"folder": "4", "dept": "dept_tiktok", "account": "@vinihack979", "name": "Mesa 4 — TikTok"},
        {"folder": "5", "dept": "dept_tiktokshop", "account": "@vinihack120", "name": "Mesa 5 — TikTok Shop"},
        {"folder": "6", "dept": "dept_youtube", "account": "@viniciusferraz218", "name": "Mesa 6 — YouTube"},
    ]

    def __init__(
        self,
        initial_account: str = "@unamyti",
        db: DatabaseManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db or DatabaseManager.get_instance()
        self.current_account = initial_account
        self.current_year = 2026
        self.current_month = 11  # Novembro
        self.selected_date_str = ""

        self.setWindowTitle("TKS Engine 3.0 — Calendário de Agendamentos do Computador")
        self.setFixedSize(620, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F1117;
                color: #FFFFFF;
                font-family: 'Segoe UI', Roboto, sans-serif;
            }
        """)

        self._build_ui()
        self._load_and_refresh()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Header do Topo
        header_row = QHBoxLayout()
        header_left = QVBoxLayout()
        header_left.setSpacing(2)

        lbl_title = QLabel("📅 Calendário de Agendamentos do Computador")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #FFFFFF;")
        
        self.lbl_subtitle = QLabel("Visualização dos slots programados no TikTok Studio")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; color: #8F95A3;")

        header_left.addWidget(lbl_title)
        header_left.addWidget(self.lbl_subtitle)
        header_row.addLayout(header_left)
        header_row.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1A1D26;
                color: #8F95A3;
                border: 1px solid #282D3B;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #262B38;
                color: #FFFFFF;
            }
        """)
        btn_close.clicked.connect(self.close)
        header_row.addWidget(btn_close)
        main_layout.addLayout(header_row)

        # Barra Seletora das 6 Mesas/Contas
        desk_bar = QHBoxLayout()
        desk_bar.setSpacing(6)
        self.desk_buttons: dict[str, QPushButton] = {}

        for desk in self.DESK_LIST:
            acc = desk["account"]
            btn = QPushButton(acc)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, a=acc: self._switch_account(a))
            self.desk_buttons[acc] = btn
            desk_bar.addWidget(btn)

        main_layout.addLayout(desk_bar)

        # Container do Calendário
        cal_container = QFrame()
        cal_container.setStyleSheet("""
            QFrame {
                background-color: #161922;
                border: 1px solid #232733;
                border-radius: 12px;
            }
        """)
        cal_layout = QVBoxLayout(cal_container)
        cal_layout.setContentsMargins(14, 12, 14, 12)
        cal_layout.setSpacing(8)

        # Navegador de Mês: < Mês Ano >
        month_nav = QHBoxLayout()
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(30, 26)
        self.btn_prev.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_prev.setStyleSheet("""
            QPushButton { background-color: #1E2330; color: #CBD5E1; border: 1px solid #2D3345; border-radius: 6px; }
            QPushButton:hover { background-color: #2D3345; color: #FFFFFF; }
        """)
        self.btn_prev.clicked.connect(self._prev_month)

        self.lbl_month_year = QLabel(f"{self.MONTH_NAMES[self.current_month - 1]} {self.current_year}")
        self.lbl_month_year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_month_year.setStyleSheet("font-size: 14px; font-weight: 800; color: #FFFFFF;")

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(30, 26)
        self.btn_next.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_next.setStyleSheet("""
            QPushButton { background-color: #1E2330; color: #CBD5E1; border: 1px solid #2D3345; border-radius: 6px; }
            QPushButton:hover { background-color: #2D3345; color: #FFFFFF; }
        """)
        self.btn_next.clicked.connect(self._next_month)

        month_nav.addWidget(self.btn_prev)
        month_nav.addWidget(self.lbl_month_year, 1)
        month_nav.addWidget(self.btn_next)
        cal_layout.addLayout(month_nav)

        # Cabeçalhos da Semana (SEG..DOM)
        week_row = QHBoxLayout()
        week_row.setSpacing(4)
        for w in self.WEEKDAY_HEADERS:
            lbl_w = QLabel(w)
            lbl_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_w.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 800;")
            week_row.addWidget(lbl_w)
        cal_layout.addLayout(week_row)

        # Grid dos Dias
        self.grid_days = QGridLayout()
        self.grid_days.setSpacing(4)
        cal_layout.addLayout(self.grid_days)

        main_layout.addWidget(cal_container)

        # Painel Inferior: Detalhes do Dia Selecionado
        self.details_frame = QFrame()
        self.details_frame.setFixedHeight(180)
        self.details_frame.setStyleSheet("""
            QFrame {
                background-color: #141720;
                border: 1px solid #232733;
                border-radius: 12px;
            }
        """)
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(14, 10, 14, 10)
        details_layout.setSpacing(6)

        # Cabeçalho dos Detalhes
        det_header = QHBoxLayout()
        self.lbl_selected_title = QLabel("Selecione um dia no calendário")
        self.lbl_selected_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #FFFFFF;")
        
        self.lbl_selected_badge = QLabel("0 de 5 agendados")
        self.lbl_selected_badge.setStyleSheet("""
            background-color: #1E2330;
            color: #84CC16;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid #84CC16;
        """)
        det_header.addWidget(self.lbl_selected_title)
        det_header.addStretch()
        det_header.addWidget(self.lbl_selected_badge)
        details_layout.addLayout(det_header)

        # Scroll Area para lista de vídeos do dia
        self.scroll_details = QScrollArea()
        self.scroll_details.setWidgetResizable(True)
        self.scroll_details.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.details_content = QWidget()
        self.details_items_layout = QVBoxLayout(self.details_content)
        self.details_items_layout.setContentsMargins(0, 0, 0, 0)
        self.details_items_layout.setSpacing(4)
        self.scroll_details.setWidget(self.details_content)
        details_layout.addWidget(self.scroll_details)

        main_layout.addWidget(self.details_frame)

    def _switch_account(self, account: str) -> None:
        self.current_account = account
        self._load_and_refresh()

    def _prev_month(self) -> None:
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._load_and_refresh()

    def _next_month(self) -> None:
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._load_and_refresh()

    def _on_day_clicked(self, date_str: str) -> None:
        self.selected_date_str = date_str
        self._render_calendar_grid()
        self._render_day_details()

    def _load_and_refresh(self) -> None:
        # Atualizar estilo dos botões das mesas
        for acc, btn in self.desk_buttons.items():
            if acc == self.current_account:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #84CC16;
                        color: #0F172A;
                        font-weight: 900;
                        font-size: 11px;
                        border-radius: 6px;
                        border: none;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1A1D26;
                        color: #8F95A3;
                        font-size: 11px;
                        border: 1px solid #282D3B;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #262B38;
                        color: #FFFFFF;
                    }
                """)

        # Atualizar título do mês
        self.lbl_month_year.setText(f"{self.MONTH_NAMES[self.current_month - 1]} {self.current_year}")

        # Buscar agendamentos da conta e departamento no SQLite
        raw_account = self.current_account.replace("@", "")
        current_dept = ""
        for d in self.DESK_LIST:
            if d["account"] == self.current_account:
                current_dept = d["dept"]
                break

        self.schedules_by_date: dict[str, list[dict[str, Any]]] = {}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, filename, schedule_time, status, caption, department_id
                    FROM jobs
                    WHERE (department_id = ? OR department_id = ? OR account_id = ? OR account_id = ? OR account_id LIKE ?)
                      AND schedule_time IS NOT NULL
                      AND status IN ('READY_FOR_UPLOAD', 'ASSIGNED', 'RUNNING', 'UPLOADING', 'PROCESSING', 'SUBMITTING', 'SCHEDULED', 'PUBLISHED', 'ARCHIVED')
                    ORDER BY schedule_time ASC
                    """,
                    (current_dept, current_dept.replace("dept_", ""), self.current_account, raw_account, f"%{raw_account}%"),
                )
                for r in cursor.fetchall():
                    s_time = str(r["schedule_time"]).strip()
                    parts = s_time.split(" ")
                    d_str = parts[0]
                    t_str = parts[1][:5] if len(parts) > 1 else "18:00"
                    item = {
                        "id": r["id"],
                        "filename": r["filename"],
                        "schedule_time": s_time,
                        "time_str": t_str,
                        "status": r["status"],
                        "caption": r["caption"] or "ABSURDO",
                    }
                    if d_str not in self.schedules_by_date:
                        self.schedules_by_date[d_str] = []
                    self.schedules_by_date[d_str].append(item)
        except Exception as e:
            print("Erro ao consultar agendamentos:", e)

        # Selecionar automaticamente o primeiro dia com agendamentos se nada selecionado
        dates = sorted(self.schedules_by_date.keys())
        if dates and (not self.selected_date_str or self.selected_date_str not in self.schedules_by_date):
            self.selected_date_str = dates[0]

        self._render_calendar_grid()
        self._render_day_details()

    def _render_calendar_grid(self) -> None:
        # Limpar grid anterior
        while self.grid_days.count():
            item = self.grid_days.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cal = calendar.Calendar(firstweekday=0) # Segunda-feira primeiro
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)

        for row_idx, week in enumerate(month_days):
            for col_idx, day_num in enumerate(week):
                if day_num == 0:
                    cell = DayCellWidget(
                        day_num=0,
                        date_str="",
                        videos=[],
                        is_current_month=False,
                        is_selected=False,
                        on_click=None,
                    )
                else:
                    d_str = f"{self.current_year:04d}-{self.current_month:02d}-{day_num:02d}"
                    vids = self.schedules_by_date.get(d_str, [])
                    is_sel = (d_str == self.selected_date_str)
                    cell = DayCellWidget(
                        day_num=day_num,
                        date_str=d_str,
                        videos=vids,
                        is_current_month=True,
                        is_selected=is_sel,
                        on_click=self._on_day_clicked,
                    )
                cell.setFixedHeight(46)
                self.grid_days.addWidget(cell, row_idx, col_idx)

    def _render_day_details(self) -> None:
        # Limpar itens anteriores
        while self.details_items_layout.count():
            item = self.details_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.selected_date_str:
            self.lbl_selected_title.setText("Nenhum dia selecionado")
            self.lbl_selected_badge.setText("0 de 5 agendados")
            return

        try:
            dt = datetime.strptime(self.selected_date_str, "%Y-%m-%d")
            weekday_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][dt.weekday()]
            self.lbl_selected_title.setText(f"{weekday_pt}, {dt.day} de {self.MONTH_NAMES[dt.month - 1]} de {dt.year}")
        except Exception:
            self.lbl_selected_title.setText(self.selected_date_str)

        vids = self.schedules_by_date.get(self.selected_date_str, [])
        self.lbl_selected_badge.setText(f"{len(vids)} de 5 agendados")

        if not vids:
            lbl_empty = QLabel("Nenhum vídeo programado para este dia.")
            lbl_empty.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic; padding: 10px;")
            self.details_items_layout.addWidget(lbl_empty)
            return

        for vid in vids:
            row_frame = QFrame()
            row_frame.setStyleSheet("""
                QFrame {
                    background-color: #1A1E29;
                    border: 1px solid #262D3D;
                    border-radius: 6px;
                }
            """)
            r_layout = QHBoxLayout(row_frame)
            r_layout.setContentsMargins(8, 6, 8, 6)
            r_layout.setSpacing(8)

            lbl_t = QLabel(vid["time_str"])
            lbl_t.setStyleSheet("""
                background-color: #84CC16;
                color: #0F172A;
                font-weight: 900;
                font-size: 11px;
                padding: 2px 6px;
                border-radius: 4px;
            """)
            r_layout.addWidget(lbl_t)

            lbl_f = QLabel(vid["filename"])
            lbl_f.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: 600;")
            r_layout.addWidget(lbl_f, 1)

            st_text = "Agendado no TikTok" if vid["status"] in ("SCHEDULED", "ARCHIVED") else "Fila de Post"
            lbl_st = QLabel(st_text)
            lbl_st.setStyleSheet("color: #10B981; font-size: 10px; font-weight: 700;")
            r_layout.addWidget(lbl_st)

            self.details_items_layout.addWidget(row_frame)

        self.details_items_layout.addStretch()
