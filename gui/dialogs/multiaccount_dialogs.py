"""Dialogs for TKS Engine multiaccount management."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.account_model import AccountRecord
from gui.widgets.tiktok_style import (
    TT_BG_HOVER,
    TT_BORDER,
    TT_FONT,
    TT_RED,
    TT_RED_HOVER,
    TT_TEXT,
    TT_TEXT_2,
)


class AssignDepartmentDialog(QDialog):
    """Dialog to assign a TikTok account to one of the 6 departments or unassign."""

    DEPARTMENTS = [
        "Não atribuído",
        "Instagram",
        "Mercado Livre",
        "Shorts",
        "TikTok",
        "TikTok Shop",
        "YouTube",
    ]

    def __init__(self, account: AccountRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Associar Departamento")
        self.setModal(True)
        self.setFixedWidth(420)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #FFFFFF;
                font-family: {TT_FONT};
                color: {TT_TEXT};
            }}
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: {TT_TEXT};
                min-height: 20px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QPushButton#saveBtn {{
                background-color: {TT_RED};
                color: #FFFFFF;
                font-weight: 700;
                border-radius: 6px;
                padding: 8px 20px;
                min-height: 22px;
                border: none;
            }}
            QPushButton#saveBtn:hover {{
                background-color: {TT_RED_HOVER};
            }}
            QPushButton#cancelBtn {{
                background-color: {TT_BG_HOVER};
                color: {TT_TEXT};
                font-weight: 600;
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 22px;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Associar Conta ao Departamento")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #161823;")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Defina a qual pasta ou departamento a conta {account.display_name} pertence."
        )
        subtitle.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.dept_combo = QComboBox()
        self.dept_combo.addItems(self.DEPARTMENTS)
        current = account.department_id or "Não atribuído"
        idx = self.dept_combo.findText(current)
        if idx >= 0:
            self.dept_combo.setCurrentIndex(idx)
        layout.addWidget(self.dept_combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Salvar Associação")
        save_btn.setObjectName("saveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def get_selected_department(self) -> str | None:
        val = self.dept_combo.currentText()
        return None if val == "Não atribuído" else val


class EditAccountIdentificationDialog(QDialog):
    """Dialog to edit account title and username handle."""

    def __init__(self, account: AccountRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Identificação da Conta")
        self.setModal(True)
        self.setFixedWidth(440)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #FFFFFF;
                font-family: {TT_FONT};
                color: {TT_TEXT};
            }}
            QLineEdit {{
                background-color: #FFFFFF;
                border: 1px solid {TT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: {TT_TEXT};
            }}
            QPushButton#saveBtn {{
                background-color: {TT_RED};
                color: #FFFFFF;
                font-weight: 700;
                border-radius: 6px;
                padding: 8px 20px;
                min-height: 22px;
                border: none;
            }}
            QPushButton#saveBtn:hover {{
                background-color: {TT_RED_HOVER};
            }}
            QPushButton#cancelBtn {{
                background-color: {TT_BG_HOVER};
                color: {TT_TEXT};
                font-weight: 600;
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 22px;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Editar Identificação")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #161823;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Rótulo / Título de Exibição:"))
        self.title_input = QLineEdit(account.display_title or "")
        self.title_input.setPlaceholderText("ex.: Conta TikTok 01")
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Nome de Usuário (@username):"))
        self.username_input = QLineEdit(account.username or "")
        self.username_input.setPlaceholderText("ex.: perfil.oficial")
        layout.addWidget(self.username_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Salvar Alterações")
        save_btn.setObjectName("saveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def get_title(self) -> str:
        return self.title_input.text().strip()

    def get_username(self) -> str:
        return self.username_input.text().lstrip("@").strip()
