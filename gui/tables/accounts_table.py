"""Accounts management table widget for TKS Engine multiaccount system."""
from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QWidget


class AccountsTable(QTableWidget):
    """Table used for multiaccount management matching Section 9 specs.

    Columns:
    0: Conta (ex: Conta TikTok 01)
    1: Usuário (ex: @username ou Pendente)
    2: Autenticação (Status badge)
    3: Departamento (ex: TikTok Shop, Não atribuído)
    4: Ações (Testar, Depto, Editar, Remover)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "grid-table")
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "Conta",
            "Usuário",
            "Autenticação",
            "Departamento",
            "Ações",
        ])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(True)
        self.viewport().setAutoFillBackground(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(54)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(4, 210)
