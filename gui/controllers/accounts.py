from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QWidget,
)

from core.account_model import AccountAuthStatus, AccountRecord
from gui.controllers.session_validation_worker import SessionValidationWorker
from gui.dialogs.account_dialog import AccountDialog
from gui.dialogs.multiaccount_dialogs import (
    AssignDepartmentDialog,
    EditAccountIdentificationDialog,
)
from gui.widgets.icon import build_icon
from gui.widgets.tiktok_style import (
    TT_BG_HOVER,
    TT_BORDER,
    TT_GREEN,
    TT_RED,
    TT_RED_HOVER,
    TT_TEXT,
    TT_TEXT_2,
)


class AccountsControllerMixin:
    """Handle account management workflows for Multiaccount TikTok Engine."""

    def _load_accounts(self) -> None:
        """Scan cookie files and registry, refresh account UI surfaces."""
        acc_mgr = self._cookie_manager.account_manager
        acc_mgr._migrate_legacy_cookies()
        all_accounts = acc_mgr.list_accounts()

        dropdown_items_set: set[str] = set()
        for acc in all_accounts:
            if acc.enabled and acc.username:
                dropdown_items_set.add(acc.username.lstrip("@"))

        for u in self._cookie_manager.list_accounts():
            dropdown_items_set.add(u.lstrip("@"))

        dropdown_items = sorted(list(dropdown_items_set))

        current_username = self._window.account_dropdown.currentText()
        self._window.account_dropdown.clear()

        if dropdown_items:
            self._window.account_dropdown.addItems(dropdown_items)
            index = self._window.account_dropdown.findText(current_username)
            if index >= 0:
                self._window.account_dropdown.setCurrentIndex(index)
            else:
                self._window.account_dropdown.setCurrentIndex(0)
        else:
            self._logger.warning("Nenhuma conta cadastrada ou ativa no sistema")
            self._window.accounts_page.accounts_current_metric.set_value("-")

        self._refresh_accounts_table()
        self._update_account_selection_summary()

    def _on_account_selected(self, username: str) -> None:
        """Handle account dropdown changes."""
        self._cached_username = username
        if username:
            self._logger.info(f"Selected account: @{username}")
            self._window.accounts_page.accounts_current_metric.set_value(f"@{username}")
            self._window.accounts_page.accounts_current_metric.set_caption("Usada na próxima execução")
            if hasattr(self._window, "stepper_bar"):
                self._window.stepper_bar.set_active_account(username)
            if hasattr(self._window, "executor_page") and hasattr(self._window.executor_page, "metric_account"):
                self._window.executor_page.metric_account.set_value(f"@{username}")
        else:
            self._window.accounts_page.accounts_current_metric.set_value("-")
            if hasattr(self._window, "stepper_bar"):
                self._window.stepper_bar.set_active_account("")
            if hasattr(self._window, "executor_page") and hasattr(self._window.executor_page, "metric_account"):
                self._window.executor_page.metric_account.set_value("-")

        # Refresh cards and table active markers without infinite recursion
        current_username = self._window.account_dropdown.currentText()
        acc_mgr = self._cookie_manager.account_manager
        all_accounts = acc_mgr.list_accounts()

        card_items = []
        for acc in all_accounts:
            user_label = acc.username or acc.display_title
            is_valid = acc.auth_status in (
                AccountAuthStatus.AUTHENTICATED.value,
                AccountAuthStatus.STRUCTURALLY_VALID.value,
            )
            card_items.append({
                "username": user_label,
                "display_name": acc.display_title or user_label,
                "session_valid": is_valid,
                "session_text": acc.auth_status,
                "last_used": acc.last_validated_at or acc.imported_at,
                "is_active": user_label == current_username or acc.username == current_username,
            })
        if hasattr(self._window.accounts_page, "populate_account_cards"):
            self._window.accounts_page.populate_account_cards(card_items)

        if self._worker is None or not self._worker.isRunning():
            self._tasks = []
            self._window.start_btn.setEnabled(False)
            if self._window.folder_dropdown.currentText() and self._videos:
                self._on_scan_clicked()

    def _on_import_json_clicked(self) -> None:
        """Batch import multiple TikTok Cookie-Editor JSON files with DPAPI protection."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self._window,
            "Selecionar Arquivos de Cookies TikTok JSON (Cookie-Editor)",
            "",
            "Arquivos JSON (*.json);;Todos os Arquivos (*.*)",
        )

        if not file_paths:
            return

        acc_mgr = self._cookie_manager.account_manager
        results = acc_mgr.import_cookie_files([Path(p) for p in file_paths])

        total_imported = len(results)
        valid_count = sum(1 for _, rep in results if rep.is_valid)
        total_cookies = sum(rep.valid_cookies for _, rep in results)

        summary_msg = (
            f"<b>Importação Concluída:</b> {total_imported} arquivo(s) processado(s).<br><br>"
            f"• <b>Contas Estruturalmente Válidas:</b> {valid_count} de {total_imported}<br>"
            f"• <b>Total de Cookies Normalizados:</b> {total_cookies}<br>"
            f"• <b>Proteção:</b> Criptografados com <b>Windows DPAPI</b> em repouso.<br><br>"
            "<i>Nenhum cookie é armazenado ou exposto em texto plano.</i><br><br>"
            "Deseja <b>remover com segurança os arquivos JSON originais</b> agora que as cópias criptografadas estão salvas?"
        )

        reply = QMessageBox.question(
            self._window,
            "Importação Concluída — Criptografia DPAPI",
            summary_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for fp in file_paths:
                try:
                    p = Path(fp)
                    if p.exists():
                        p.unlink()
                        deleted_count += 1
                except Exception as exc:
                    self._logger.warning(f"Não foi possível apagar {fp}: {exc}")
            self._logger.info(f"Removidos {deleted_count} arquivos JSON originais desprotegidos.")

        self._logger.success(f"Importadas {total_imported} conta(s) com sucesso.")
        self._load_accounts()

    def _refresh_accounts_table(self, accounts: list[str] | None = None) -> None:
        """Populate the 5-column account management table matching Section 9."""
        acc_mgr = self._cookie_manager.account_manager
        all_accounts = acc_mgr.list_accounts()

        table = self._window.accounts_table
        table.setRowCount(len(all_accounts))
        current_username = self._window.account_dropdown.currentText()

        for row_index, acc in enumerate(all_accounts):
            # Col 0: Conta (Nome/Título da conta)
            conta_label = acc.display_title or f"Conta TikTok {row_index + 1:02d}"
            item_conta = QTableWidgetItem(conta_label)
            item_conta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, 0, item_conta)

            # Col 1: Usuário (@username ou pendente)
            user_label = f"@{acc.username}" if acc.username else "Pendente de validação"
            item_user = QTableWidgetItem(user_label)
            item_user.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, 1, item_user)

            # Col 2: Autenticação (Badge visual com estado estrito)
            status_widget = self._build_auth_status_badge(acc.auth_status, acc.enabled)
            table.setCellWidget(row_index, 2, status_widget)

            # Col 3: Departamento
            dept_label = acc.department_id or "Não atribuído"
            item_dept = QTableWidgetItem(dept_label)
            item_dept.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, 3, item_dept)

            # Col 4: Ações (Testar, Depto, Editar, Desativar, Remover)
            actions_widget = self._build_multiaccount_actions(acc)
            table.setCellWidget(row_index, 4, actions_widget)

        table.resizeColumnsToContents()
        table.setColumnWidth(4, max(table.columnWidth(4), 220))
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for row in range(table.rowCount()):
            table.setRowHeight(row, 54)

        active_count = sum(1 for a in all_accounts if a.enabled)
        self._window.accounts_page.accounts_total_metric.set_value(str(len(all_accounts)))
        self._window.accounts_page.accounts_selected_metric.set_value(str(active_count))

        # Rebuild visual cards
        card_items = []
        for acc in all_accounts:
            user_label = acc.username or acc.display_title
            is_valid = acc.auth_status in (
                AccountAuthStatus.AUTHENTICATED.value,
                AccountAuthStatus.STRUCTURALLY_VALID.value,
            )
            card_items.append({
                "username": user_label,
                "display_name": acc.display_title or user_label,
                "session_valid": is_valid,
                "session_text": acc.auth_status,
                "last_used": acc.last_validated_at or acc.imported_at,
                "is_active": user_label == current_username or acc.username == current_username,
            })
        if hasattr(self._window.accounts_page, "populate_account_cards"):
            self._window.accounts_page.populate_account_cards(card_items)

    def _build_auth_status_badge(self, status: str, enabled: bool) -> QWidget:
        """Create colored status badge for authentication state."""
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel(status if enabled else "DISABLED")

        if not enabled or status == AccountAuthStatus.DISABLED.value:
            badge.setStyleSheet("background: #F3F4F6; color: #9CA3AF; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        elif status == AccountAuthStatus.AUTHENTICATED.value:
            badge.setStyleSheet("background: #E6F9EE; color: #00B649; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        elif status == AccountAuthStatus.VALIDATING.value:
            badge.setStyleSheet("background: #EFF6FF; color: #2563EB; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        elif status == AccountAuthStatus.STRUCTURALLY_VALID.value:
            badge.setStyleSheet("background: #E0F2FE; color: #0284C7; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        elif status == AccountAuthStatus.INVALID_SESSION.value:
            badge.setStyleSheet("background: #FEE2E2; color: #DC2626; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        elif status == AccountAuthStatus.EXPIRED.value:
            badge.setStyleSheet("background: #FEF3D6; color: #D97706; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        elif status in (AccountAuthStatus.VALIDATION_REQUIRED.value, AccountAuthStatus.REAUTH_REQUIRED.value):
            badge.setStyleSheet("background: #FEF9C3; color: #CA8A04; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")
        else:
            badge.setStyleSheet("background: #F3F4F6; color: #4B5563; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 3px 10px;")

        lay.addWidget(badge)
        return container

    def _build_multiaccount_actions(self, acc: AccountRecord) -> QWidget:
        """Build action buttons for account row (Test, Dept, Edit, Disable/Enable, Delete)."""
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Test / Validate Session button
        test_btn = QPushButton()
        test_btn.setFixedSize(30, 30)
        test_btn.setToolTip("Testar / Validar Sessão (Modo Leitura)")
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.setIcon(build_icon("fa5s.sync-alt", "#0284C7"))
        test_btn.setStyleSheet(f"border: 1px solid {TT_BORDER}; border-radius: 4px; background: #FFFFFF;")
        test_btn.clicked.connect(lambda: self._test_account_session(acc.account_id))
        lay.addWidget(test_btn)

        # 2. Assign Department button
        dept_btn = QPushButton()
        dept_btn.setFixedSize(30, 30)
        dept_btn.setToolTip("Associar Departamento")
        dept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dept_btn.setIcon(build_icon("fa5.folder", TT_TEXT))
        dept_btn.setStyleSheet(f"border: 1px solid {TT_BORDER}; border-radius: 4px; background: #FFFFFF;")
        dept_btn.clicked.connect(lambda: self._assign_department(acc.account_id))
        lay.addWidget(dept_btn)

        # 3. Edit Identification button
        edit_btn = QPushButton()
        edit_btn.setFixedSize(30, 30)
        edit_btn.setToolTip("Editar Rótulo ou Usuário")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setIcon(build_icon("fa5s.edit", TT_TEXT))
        edit_btn.setStyleSheet(f"border: 1px solid {TT_BORDER}; border-radius: 4px; background: #FFFFFF;")
        edit_btn.clicked.connect(lambda: self._edit_account_identification(acc.account_id))
        lay.addWidget(edit_btn)

        # 4. Toggle Enabled / Disabled
        toggle_btn = QPushButton()
        toggle_btn.setFixedSize(30, 30)
        toggle_btn.setToolTip("Desativar Conta" if acc.enabled else "Ativar Conta")
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_icon = "fa5s.toggle-on" if acc.enabled else "fa5s.toggle-off"
        toggle_color = TT_GREEN if acc.enabled else TT_TEXT_2
        toggle_btn.setIcon(build_icon(toggle_icon, toggle_color))
        toggle_btn.setStyleSheet(f"border: 1px solid {TT_BORDER}; border-radius: 4px; background: #FFFFFF;")
        toggle_btn.clicked.connect(lambda: self._toggle_account_enabled(acc.account_id))
        lay.addWidget(toggle_btn)

        # 5. Delete Account button
        del_btn = QPushButton()
        del_btn.setFixedSize(30, 30)
        del_btn.setToolTip("Remover Conta")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setIcon(build_icon("fa5s.trash-alt", TT_RED))
        del_btn.setStyleSheet("border: 1px solid #FEE2E2; border-radius: 4px; background: #FFF1F3;")
        del_btn.clicked.connect(lambda: self._delete_single_account(acc.account_id))
        lay.addWidget(del_btn)

        return container

    def _test_account_session(self, account_id: str) -> None:
        """Validate account session in read-only mode via background worker."""
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account(account_id)
        if not acc:
            return

        acc_mgr.update_account(account_id, auth_status=AccountAuthStatus.VALIDATING.value)
        self._refresh_accounts_table()
        self._logger.info(f"Iniciando validação de sessão (modo leitura) para {acc.display_name}...")

        worker = SessionValidationWorker(acc_mgr, account_id, headless=True)
        worker.validation_finished.connect(self._on_session_validation_finished)
        # Keep worker reference alive
        self._validation_workers = getattr(self, "_validation_workers", [])
        self._validation_workers.append(worker)
        worker.start()

    def _on_session_validation_finished(
        self,
        account_id: str,
        is_auth: bool,
        msg: str,
        detected_user: str,
    ) -> None:
        """Handle completion of background session validation."""
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account(account_id)
        acc_name = acc.display_name if acc else account_id[:8]

        if is_auth:
            self._logger.success(f"Validação de sessão bem-sucedida para {acc_name}: {msg}")
            QMessageBox.information(
                self._window,
                "Sessão Autenticada",
                f"A sessão de <b>{acc_name}</b> foi validada com sucesso no TikTok Studio!<br>"
                f"Usuário identificado: <b>@{detected_user or acc.username}</b>",
            )
        else:
            self._logger.warning(f"Resultado da validação para {acc_name}: {msg}")
            QMessageBox.warning(
                self._window,
                "Resultado da Validação",
                f"Validação para <b>{acc_name}</b>:<br><br>{msg}",
            )

        self._load_accounts()

    def _assign_department(self, account_id: str) -> None:
        """Open dialog to assign account to one of the 6 departments."""
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account(account_id)
        if not acc:
            return

        dlg = AssignDepartmentDialog(acc, parent=self._window)
        if dlg.exec():
            dept = dlg.get_selected_department()
            acc_mgr.update_account(account_id, department_id=dept)
            self._logger.info(f"Conta {acc.display_name} associada ao departamento '{dept or 'Não atribuído'}'")
            self._load_accounts()

    def _edit_account_identification(self, account_id: str) -> None:
        """Open dialog to edit account title and username."""
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account(account_id)
        if not acc:
            return

        dlg = EditAccountIdentificationDialog(acc, parent=self._window)
        if dlg.exec():
            new_title = dlg.get_title()
            new_user = dlg.get_username()
            acc.display_title = new_title
            acc_mgr.update_account(account_id, username=new_user)
            self._logger.info(f"Identificação atualizada para {acc.display_name}")
            self._load_accounts()

    def _toggle_account_enabled(self, account_id: str) -> None:
        """Toggle account enabled/disabled state."""
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account(account_id)
        if not acc:
            return

        new_state = not acc.enabled
        acc_mgr.update_account(account_id, enabled=new_state)
        self._logger.info(f"Conta {acc.display_name} {'ativada' if new_state else 'desativada'}")
        self._load_accounts()

    def _delete_single_account(self, account_id: str) -> None:
        """Remove account record and secure DPAPI credentials with user confirmation."""
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account(account_id)
        if not acc:
            return

        reply = QMessageBox.question(
            self._window,
            "Confirmar Remoção de Conta",
            f"Deseja realmente remover o cadastro e as credenciais protegidas da conta <b>{acc.display_name}</b>?<br><br>"
            "<i>Nota: Históricos de agendamentos e publicações anteriores são preservados.</i>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            acc_mgr.delete_account(account_id, delete_credentials=True)
            self._logger.success(f"Conta {acc.display_name} removida.")
            self._load_accounts()

    def _on_add_account_clicked(self) -> None:
        """Open manual JSON paste dialog."""
        dialog = AccountDialog("Adicionar conta", parent=self._window)
        dialog.save_btn.clicked.connect(lambda: self._save_new_account(dialog))
        dialog.exec()

    def _on_edit_account_clicked(self) -> None:
        """Edit currently selected account from table."""
        usernames = self._selected_account_usernames()
        if not usernames:
            self._logger.warning("Selecione uma conta na tabela para editar")
            return

        username = usernames[0]
        acc_mgr = self._cookie_manager.account_manager
        acc = acc_mgr.get_account_by_username(username)
        if acc:
            self._edit_account_identification(acc.account_id)
        else:
            self._edit_account(username)

    def _on_random_account_requested(self) -> None:
        """Pick a random active account."""
        dropdown = self._window.account_dropdown
        count = dropdown.count()
        if count <= 0:
            self._logger.warning("Nenhuma conta disponível para sorteio")
            return

        rand_idx = random.randint(0, count - 1)
        dropdown.setCurrentIndex(rand_idx)
        self._logger.info(f"Conta sorteada: @{dropdown.currentText()}")

    def _on_account_card_selected(self, username: str) -> None:
        """Select account from card and advance to Step 2 (Videos)."""
        clean = username.lstrip("@")
        index = self._window.account_dropdown.findText(clean)
        if index >= 0:
            self._window.account_dropdown.setCurrentIndex(index)
        self._on_account_selected(clean)
        if hasattr(self, "_save_wizard_state"):
            self._save_wizard_state()
        if hasattr(self, "_go_to_wizard_step"):
            self._go_to_wizard_step(1)
        elif hasattr(self._window, "set_wizard_step"):
            self._window.set_wizard_step(1)

    def _edit_account(self, username: str) -> None:
        """Select row and open edit."""
        table = self._window.accounts_table
        for row in range(table.rowCount()):
            item = table.item(row, 1)
            if item is not None and item.text().lstrip("@") == username:
                table.selectRow(row)
                break
        self._on_edit_account_clicked()

    def _update_account_selection_summary(self) -> None:
        """Refresh selection metric."""
        selected_count = len(self._selected_account_usernames())
        self._window.accounts_page.accounts_selected_metric.set_value(str(selected_count))

    def _save_new_account(self, dialog: AccountDialog) -> None:
        """Validate and save a new account via manual paste dialog."""
        username, cookie_data = self._validate_account_dialog(dialog)
        if username is None or cookie_data is None:
            return

        acc_mgr = self._cookie_manager.account_manager
        # Save temp json and import
        temp_dir = self._cookies_dir / "temp_import"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"@{username}-cookie.json"

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, indent=2, ensure_ascii=False)
            acc_mgr.import_cookie_files([temp_file])
            temp_file.unlink(missing_ok=True)
        except Exception as exc:
            dialog.show_error(f"Falha ao salvar conta: {exc}")
            return

        self._logger.success(f"Conta @{username} adicionada com sucesso.")
        dialog.accept()
        self._load_accounts()

    def _validate_account_dialog(
        self,
        dialog: AccountDialog,
    ) -> tuple[str | None, list[dict] | None]:
        """Validate dialog fields."""
        dialog.clear_error()
        username = dialog.get_username()
        cookie_text = dialog.get_cookie_text()

        if not username:
            dialog.show_error("Usuário é obrigatório.")
            return None, None
        username = username.lstrip("@").strip()
        if not re.match(r"^[\w.]+$", username):
            dialog.show_error("Nome de usuário com caracteres inválidos.")
            return None, None

        if not cookie_text:
            dialog.show_error("Cookies JSON é obrigatório.")
            return None, None

        try:
            cookie_data = json.loads(cookie_text)
        except json.JSONDecodeError as exc:
            dialog.show_error(f"JSON inválido: {exc}")
            return None, None

        if not isinstance(cookie_data, list) or len(cookie_data) == 0:
            dialog.show_error("Cookies JSON deve ser um array não vazio.")
            return None, None

        return username, cookie_data

    def _on_delete_accounts_clicked(self) -> None:
        """Delete selected accounts."""
        usernames = self._selected_account_usernames()
        if not usernames:
            self._logger.warning("Selecione pelo menos uma conta para remover")
            return
        self._delete_accounts(usernames)

    def _delete_accounts(self, usernames: list[str]) -> None:
        """Delete account records by usernames."""
        acc_mgr = self._cookie_manager.account_manager
        for u in usernames:
            acc = acc_mgr.get_account_by_username(u)
            if acc:
                acc_mgr.delete_account(acc.account_id, delete_credentials=True)
            else:
                p = self._cookies_dir / f"@{u}-cookie.json"
                if p.exists():
                    p.unlink(missing_ok=True)
        self._load_accounts()

    def _selected_account_usernames(self) -> list[str]:
        """Return usernames selected in table."""
        usernames: list[str] = []
        table = self._window.accounts_table
        for item in table.selectedItems():
            row = item.row()
            username_item = table.item(row, 1)
            if username_item is None:
                continue
            username = username_item.text().lstrip("@")
            if username not in usernames and username != "Pendente de validação":
                usernames.append(username)
        return usernames
