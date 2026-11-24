"""Accounts page (Step 1): Multiaccount management and selection for TKS Engine."""
from __future__ import annotations

import hashlib
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.tables.accounts_table import AccountsTable
from gui.widgets.icon import build_icon
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
    hline,
)


class InlineStat(QWidget):
    """Inline metric text block."""

    def __init__(
        self,
        title: str,
        value: str,
        caption: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet("border: none; background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {TT_TEXT_2}; letter-spacing: 0.5px; border: none; background: transparent;"
        )
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {TT_RED}; border: none; background: transparent;"
        )
        layout.addWidget(self.value_label)

        self.caption_label = QLabel(caption)
        self.caption_label.setStyleSheet(
            f"font-size: 11px; color: {TT_TEXT_2}; border: none; background: transparent;"
        )
        layout.addWidget(self.caption_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_caption(self, caption: str) -> None:
        self.caption_label.setText(caption)


def build_avatar_pixmap(username: str, size: int = 46) -> QPixmap:
    """Generate a circular avatar badge with initials on vibrant background."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    digest = hashlib.md5(username.encode("utf-8")).hexdigest()
    palette_pairs = [
        ("#7C3AED", "#6D28D9"),
        ("#2563EB", "#1D4ED8"),
        ("#059669", "#047857"),
        ("#DB2777", "#BE185D"),
        ("#EA580C", "#C2410C"),
    ]
    c1, c2 = palette_pairs[int(digest[:2], 16) % len(palette_pairs)]

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor(c1))
    grad.setColorAt(1.0, QColor(c2))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)

    initials = (username.strip().lstrip("@")[:2] or "TK").upper()
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 13, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return pix


class AccountCardWidget(QFrame):
    """Visual card representing a registered TikTok account."""

    select_clicked = pyqtSignal(str)
    edit_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)

    def __init__(
        self,
        username: str,
        display_name: str,
        session_valid: bool,
        session_text: str,
        last_used: str,
        is_active: bool,
        icon_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._username = username
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self.setStyleSheet(f"""
            AccountCardWidget {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton#cardEditBtn, QPushButton#cardDelBtn {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 6px;
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
            }}
            QPushButton#cardEditBtn:hover {{
                background-color: {TT_BG_HOVER};
            }}
            QPushButton#cardDelBtn:hover {{
                background-color: #FFF1F3;
            }}
            QPushButton#cardSelectBtn {{
                background-color: {TT_RED};
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                border-radius: 6px;
                min-height: 36px;
                border: none;
            }}
            QPushButton#cardSelectBtn:hover {{
                background-color: {TT_RED_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(10)

        # Top row
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        avatar_label = QLabel()
        avatar_label.setPixmap(build_avatar_pixmap(username, 46))
        avatar_label.setFixedSize(46, 46)
        top_row.addWidget(avatar_label)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        title_lbl = QLabel(display_name)
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TT_TEXT};")
        name_col.addWidget(title_lbl)

        user_lbl = QLabel(f"@{username}" if username and not username.startswith("Conta TikTok") else username)
        user_lbl.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
        name_col.addWidget(user_lbl)
        top_row.addLayout(name_col, 1)

        edit_btn = QPushButton()
        edit_btn.setObjectName("cardEditBtn")
        edit_btn.setToolTip("Editar identificação")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setIcon(build_icon("fa5s.edit", TT_TEXT))
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._username))
        top_row.addWidget(edit_btn)

        del_btn = QPushButton()
        del_btn.setObjectName("cardDelBtn")
        del_btn.setToolTip("Remover conta")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setIcon(build_icon("fa5s.trash-alt", TT_RED))
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._username))
        top_row.addWidget(del_btn)

        layout.addLayout(top_row)

        # Status badge
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        badge = QLabel(session_text)
        badge_style = (
            "background: #E6F9EE; color: #00B649; font-size: 11px; font-weight: 600; border-radius: 10px; padding: 3px 10px;"
            if session_valid else
            "background: #FEE2E2; color: #EF4444; font-size: 11px; font-weight: 600; border-radius: 10px; padding: 3px 10px;"
        )
        badge.setStyleSheet(badge_style)
        status_row.addWidget(badge)

        if is_active:
            active_badge = QLabel("Selecionada")
            active_badge.setStyleSheet(
                "background: #FEF3D6; color: #D97706; font-size: 11px; font-weight: 600; border-radius: 10px; padding: 3px 10px;"
            )
            status_row.addWidget(active_badge)

        status_row.addStretch(1)
        layout.addLayout(status_row)

        meta_lbl = QLabel(f"Atividade: {last_used}")
        meta_lbl.setStyleSheet(f"font-size: 11px; color: {TT_TEXT_2};")
        layout.addWidget(meta_lbl)

        select_btn = QPushButton("Continuar com esta conta →" if is_active else "Selecionar e Continuar →")
        select_btn.setObjectName("cardSelectBtn")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.clicked.connect(lambda: self.select_clicked.emit(self._username))
        layout.addWidget(select_btn)


class AccountsPage(QWidget):
    """GERENCIADOR DE CONTAS TIKTOK: Full multiaccount table and card management."""

    TITLE = "1. Escolher Conta TikTok"
    DESCRIPTION = "Selecione o perfil TikTok para agendamento ou gerencie contas com proteção DPAPI."

    account_card_selected = pyqtSignal(str)
    account_card_edit = pyqtSignal(str)
    account_card_delete = pyqtSignal(str)
    open_publications_requested = pyqtSignal()
    switch_account_requested = pyqtSignal()

    def __init__(self, icon_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_color = icon_color
        self.setStyleSheet(f"""
            AccountsPage {{
                background-color: #F8F8F8;
                font-family: {TT_FONT};
            }}
            QLabel {{
                background: transparent;
                font-family: {TT_FONT};
            }}
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background-color: #F8F8F8;
                border: none;
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #F8F8F8;")
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(28, 24, 28, 24)
        self.content_layout.setSpacing(18)

        # 1. Header Card
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 12px;
            }}
        """)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(16)

        title_row = QHBoxLayout()
        title_row.setSpacing(14)

        icon_badge = QLabel()
        icon_badge.setFixedSize(42, 42)
        icon_badge.setStyleSheet("background-color: #FFF1F3; border-radius: 8px;")
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setPixmap(build_icon("fa5s.users", TT_RED).pixmap(22, 22))
        title_row.addWidget(icon_badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_text = QLabel("GERENCIADOR DE CONTAS TIKTOK")
        title_text.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {TT_TEXT}; letter-spacing: 0.5px;")
        subtitle_text = QLabel(
            "Importação em lote de cookies JSON, validação de sessões em modo leitura e armazenamento protegido com criptografia Windows DPAPI."
        )
        subtitle_text.setStyleSheet(f"font-size: 13px; color: {TT_TEXT_2};")
        subtitle_text.setWordWrap(True)
        title_col.addWidget(title_text)
        title_col.addWidget(subtitle_text)
        title_row.addLayout(title_col, 1)

        header_layout.addLayout(title_row)
        header_layout.addWidget(hline())

        # Metrics and Action Buttons
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 4, 0, 0)
        stats_row.setSpacing(32)

        self.accounts_total_metric = InlineStat("Contas Conectadas", "0", "Perfis cadastrados")
        self.accounts_selected_metric = InlineStat("Selecionadas", "0", "Perfis marcados")
        self.accounts_current_metric = InlineStat("Conta Ativa", "-", "Usada na próxima execução")
        stats_row.addWidget(self.accounts_total_metric)
        stats_row.addWidget(self.accounts_selected_metric)
        stats_row.addWidget(self.accounts_current_metric)
        stats_row.addStretch(1)

        # Primary Button: + IMPORTAR CONTAS JSON (multi-file)
        self.import_json_btn = QPushButton("+ IMPORTAR CONTAS JSON")
        self.import_json_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_json_btn.setIcon(build_icon("fa5s.file-import", "#FFFFFF"))
        self.import_json_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TT_RED};
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 800;
                border-radius: 6px;
                min-height: 40px;
                padding: 0 20px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {TT_RED_HOVER};
            }}
        """)
        stats_row.addWidget(self.import_json_btn)

        # Secondary Button: Adicionar Manual
        self.add_account_btn = QPushButton("+ Adicionar Manual")
        self.add_account_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_account_btn.setIcon(build_icon("fa5s.user-plus", TT_TEXT))
        self.add_account_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {TT_TEXT};
                border: 1px solid {TT_BORDER};
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
                min-height: 40px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {TT_BG_HOVER};
            }}
        """)
        stats_row.addWidget(self.add_account_btn)

        self.accounts_random_btn = QPushButton("Sortear Conta")
        self.accounts_random_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accounts_random_btn.setIcon(build_icon("fa5s.random", TT_TEXT))
        self.accounts_random_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {TT_TEXT};
                border: 1px solid {TT_BORDER};
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
                min-height: 40px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {TT_BG_HOVER};
            }}
        """)
        stats_row.addWidget(self.accounts_random_btn)

        self.multiaccount_central_btn = QPushButton("Central Multiaccount")
        self.multiaccount_central_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.multiaccount_central_btn.setIcon(build_icon("fa5s.server", TT_TEXT))
        self.multiaccount_central_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #F8F9FA;
                color: {TT_TEXT};
                border: 1px solid {TT_BORDER};
                font-size: 13px;
                font-weight: 700;
                border-radius: 6px;
                min-height: 40px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: #EDF2F7;
            }}
        """)
        self.multiaccount_central_btn.clicked.connect(self._open_multiaccount_central)
        stats_row.addWidget(self.multiaccount_central_btn)

        # Hidden buttons for compatibility
        self.accounts_edit_btn = QPushButton("Edit")
        self.accounts_edit_btn.hide()
        self.accounts_delete_btn = QPushButton("Delete")
        self.accounts_delete_btn.hide()

        header_layout.addLayout(stats_row)
        self.content_layout.addWidget(header_card)

        # 2. Section: Tabela de Gerenciamento de Contas
        table_card = QFrame()
        table_card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 12px;
            }}
        """)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 18, 20, 18)
        table_layout.setSpacing(12)

        table_header = QHBoxLayout()
        table_title = QLabel("TABELA DE CONTAS E SESSÕES")
        table_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {TT_TEXT};")
        table_header.addWidget(table_title)
        table_header.addStretch(1)

        table_desc = QLabel("Criptografia DPAPI em repouso · Validação em Modo Leitura")
        table_desc.setStyleSheet(f"font-size: 11px; color: {TT_TEXT_2};")
        table_header.addWidget(table_desc)
        table_layout.addLayout(table_header)

        self.accounts_table = AccountsTable()
        self.accounts_table.setMinimumHeight(240)
        table_layout.addWidget(self.accounts_table)

        self.content_layout.addWidget(table_card)

        # 3. Section: Cards Visuais (Para seleção rápida para a Etapa 2)
        cards_title = QLabel("SELEÇÃO RÁPIDA DE PERFIL")
        cards_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {TT_TEXT}; padding-top: 6px;")
        self.content_layout.addWidget(cards_title)

        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        self.cards_grid = QGridLayout(cards_container)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setHorizontalSpacing(16)
        self.cards_grid.setVerticalSpacing(16)
        self.content_layout.addWidget(cards_container)

        self.content_layout.addStretch(1)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def populate_account_cards(self, card_items: list[dict[str, Any]]) -> None:
        """Rebuild the grid of account cards."""
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        cols = 3 if len(card_items) >= 3 else 2
        for idx, info in enumerate(card_items):
            card = AccountCardWidget(
                username=str(info["username"]),
                display_name=str(info.get("display_name") or info["username"]),
                session_valid=bool(info.get("session_valid", True)),
                session_text=str(info.get("session_text", "Conectada")),
                last_used=str(info.get("last_used", "-")),
                is_active=bool(info.get("is_active", False)),
                icon_color=self._icon_color,
            )
            card.select_clicked.connect(self.account_card_selected.emit)
            card.edit_clicked.connect(self.account_card_edit.emit)
            card.delete_clicked.connect(self.account_card_delete.emit)
            self.cards_grid.addWidget(card, idx // cols, idx % cols)

    def _open_multiaccount_central(self) -> None:
        """Open the Multiaccount Execution Central dashboard dialog."""
        from gui.dialogs.multiaccount_central_dialog import MultiaccountExecutionCentralDialog
        dialog = MultiaccountExecutionCentralDialog(parent=self)
        dialog.exec()
