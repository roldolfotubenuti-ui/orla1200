from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
  QAbstractItemView,
  QComboBox,
  QDialog,
  QHBoxLayout,
  QHeaderView,
  QLabel,
  QLineEdit,
  QPushButton,
  QSpinBox,
  QTableWidget,
  QTableWidgetItem,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

from gui.widgets.tiktok_style import (
  TT_BORDER,
  TT_GREEN,
  TT_RED,
  TT_TEXT,
  TT_TEXT_2,
  hline,
  tt_base_stylesheet,
)
from utils.datetime_utils import DateTimeUtils

CAPTION_MAX = 4000


def _dialog_style() -> str:
  return tt_base_stylesheet() + "QDialog { background: #FFFFFF; }"


def _title(text: str) -> QLabel:
  lbl = QLabel(text)
  lbl.setStyleSheet("font-size: 18px; font-weight: 700;")
  return lbl


def compose_caption(caption: str, hashtags: str) -> str:
  """Join caption + hashtags exactly as the user typed (no automatic prefix)."""
  cap = caption.strip()
  tags = " ".join(
    t if t.startswith("#") else f"#{t}" for t in hashtags.replace(",", " ").split() if t.strip()
  )
  if cap and tags:
    return f"{cap} {tags}"
  return cap or tags


class CaptionEditDialog(QDialog):
  """Full caption editor: caption, hashtags, counter and live preview."""

  def __init__(self, filename: str, caption: str, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setWindowTitle("Editar legenda")
    self.setModal(True)
    self.resize(560, 420)
    self.setStyleSheet(_dialog_style())

    lay = QVBoxLayout(self)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(10)
    lay.addWidget(_title("Legenda"))
    sub = QLabel(filename)
    sub.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 12px;")
    lay.addWidget(sub)

    self.caption_edit = QTextEdit()
    self.caption_edit.setAcceptRichText(False)
    self.caption_edit.setPlainText(caption)
    self.caption_edit.setMinimumHeight(110)
    self.caption_edit.textChanged.connect(self._refresh)
    lay.addWidget(self.caption_edit)

    tags_lbl = QLabel("Hashtags")
    tags_lbl.setStyleSheet("font-weight: 600;")
    lay.addWidget(tags_lbl)
    self.hashtags_edit = QLineEdit()
    self.hashtags_edit.setPlaceholderText("#fyp #viral  (opcional — adicionadas ao final da legenda)")
    self.hashtags_edit.textChanged.connect(self._refresh)
    lay.addWidget(self.hashtags_edit)

    self.counter = QLabel()
    self.counter.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 12px;")
    lay.addWidget(self.counter, 0, Qt.AlignmentFlag.AlignRight)

    prev_t = QLabel("Prévia da legenda enviada")
    prev_t.setStyleSheet("font-weight: 600;")
    lay.addWidget(prev_t)
    self.preview = QLabel()
    self.preview.setWordWrap(True)
    self.preview.setStyleSheet(
      f"background: #F7F7F7; border: 1px solid {TT_BORDER}; border-radius: 6px; padding: 8px; color: {TT_TEXT};"
    )
    lay.addWidget(self.preview)
    lay.addStretch(1)

    btns = QHBoxLayout()
    btns.addStretch(1)
    cancel = QPushButton("Cancelar")
    cancel.setObjectName("ttSecondary")
    cancel.clicked.connect(self.reject)
    btns.addWidget(cancel)
    self.save_btn = QPushButton("Salvar")
    self.save_btn.setObjectName("ttPrimary")
    self.save_btn.clicked.connect(self.accept)
    btns.addWidget(self.save_btn)
    lay.addLayout(btns)
    self._refresh()

  def full_caption(self) -> str:
    return compose_caption(self.caption_edit.toPlainText(), self.hashtags_edit.text())

  def _refresh(self) -> None:
    full = self.full_caption()
    n = len(full)
    over = n > CAPTION_MAX
    self.counter.setText(f"{n} / {CAPTION_MAX}")
    self.counter.setStyleSheet(f"color: {TT_RED if over else TT_TEXT_2}; font-size: 12px;")
    self.preview.setText(full or "(sem legenda)")
    self.save_btn.setEnabled(not over)


class PublishConfirmDialog(QDialog):
  """Review dialog shown before the queue is prepared for execution."""

  def __init__(self, items: list[dict[str, Any]], account: str, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setWindowTitle("Confirmar publicação")
    self.setModal(True)
    self.resize(860, 520)
    self.setStyleSheet(_dialog_style() + f"""
      QTableWidget {{ background: #FFFFFF; border: 1px solid {TT_BORDER}; border-radius: 6px;
        gridline-color: transparent; color: {TT_TEXT}; }}
      QTableWidget::item {{ border-bottom: 1px solid #F1F1F2; padding: 4px; }}
      QTableWidget::item:selected {{ background: #F7F7F7; color: {TT_TEXT}; }}
      QHeaderView::section {{ background: #FFFFFF; color: {TT_TEXT_2}; font-weight: 600; border: none;
        border-bottom: 1px solid {TT_BORDER}; padding: 8px 6px; }}
    """)

    lay = QVBoxLayout(self)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(12)
    lay.addWidget(_title(f"Revisar {len(items)} publicação(ões)"))
    info = QLabel(
      f"Conta: <b>@{account}</b> — nada é enviado agora. Após confirmar, a fila é preparada "
      "e o envio só começa quando você clicar em <b>EXECUTE</b> na tela de publicação."
    )
    info.setWordWrap(True)
    info.setStyleSheet(f"color: {TT_TEXT_2};")
    lay.addWidget(info)

    self.table = QTableWidget(len(items), 5)
    self.table.setHorizontalHeaderLabels(["#", "Arquivo", "Legenda", "Programado", "Visibilidade"])
    self.table.verticalHeader().setVisible(False)
    self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    self.table.setShowGrid(False)
    hh = self.table.horizontalHeader()
    hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

    self.invalid_count = 0
    for r, it in enumerate(items):
      sched = it.get("schedule_dt")
      if isinstance(sched, datetime):
        valid = DateTimeUtils.is_valid_schedule_time(sched, 25, 10)
        when = sched.strftime("%d/%m/%Y %H:%M") + ("" if valid else "  ⚠ fora da janela (25m - 10d)")
      else:
        valid = True
        when = "Publicar agora"
      if not valid:
        self.invalid_count += 1
      cells = [
        str(r + 1),
        str(it.get("filename", "")),
        str(it.get("caption") or "(sem legenda)"),
        when,
        str(it.get("visibility", "Público")),
      ]
      for c, txt in enumerate(cells):
        cell = QTableWidgetItem(txt)
        cell.setToolTip(txt)
        if c == 3 and not valid:
          cell.setForeground(Qt.GlobalColor.red)
        self.table.setItem(r, c, cell)
      self.table.setRowHeight(r, 36)
    lay.addWidget(self.table, 1)

    now_count = sum(1 for it in items if not isinstance(it.get("schedule_dt"), datetime))
    notes = []
    if now_count:
      notes.append(f"{now_count} vídeo(s) em “Publicar agora” serão publicados imediatamente ao executar.")
    if self.invalid_count:
      notes.append(
        f"{self.invalid_count} horário(s) fora da janela permitida (mín. 25 min, máx. 10 dias). Ajuste antes de continuar."
      )
    self.note = QLabel("  ".join(notes))
    self.note.setWordWrap(True)
    self.note.setStyleSheet(f"color: {TT_RED if self.invalid_count else TT_TEXT_2}; font-size: 12px;")
    lay.addWidget(self.note)

    lay.addWidget(hline())
    btns = QHBoxLayout()
    btns.addStretch(1)
    cancel = QPushButton("Voltar e editar")
    cancel.setObjectName("ttSecondary")
    cancel.clicked.connect(self.reject)
    btns.addWidget(cancel)
    self.confirm_btn = QPushButton(f"Confirmar ({len(items)})")
    self.confirm_btn.setObjectName("ttPrimary")
    self.confirm_btn.setEnabled(self.invalid_count == 0 and len(items) > 0)
    self.confirm_btn.clicked.connect(self.accept)
    btns.addWidget(self.confirm_btn)
    lay.addLayout(btns)


class BatchScheduleDialog(QDialog):
  """Distribute loaded videos automatically across days/time window."""

  applied = pyqtSignal(int, str, str, int)

  def __init__(self, total_videos: int, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setWindowTitle("Agendar em lote")
    self.setModal(True)
    self.setFixedWidth(440)
    self.setStyleSheet(_dialog_style())

    lay = QVBoxLayout(self)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(12)
    lay.addWidget(_title("Agendar em lote"))
    desc = QLabel(
      f"Distribuir {total_videos} vídeo(s) a partir do próximo horário válido. "
      "Os limites reais da plataforma continuam valendo."
    )
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color: {TT_TEXT_2};")
    lay.addWidget(desc)

    def row(label: str, widget: QWidget, extra: QWidget | None = None) -> None:
      h = QHBoxLayout()
      lbl = QLabel(label)
      lbl.setFixedWidth(170)
      h.addWidget(lbl)
      h.addWidget(widget)
      if extra is not None:
        h.addWidget(extra)
      h.addStretch(1)
      lay.addLayout(h)

    self.per_day_spin = QSpinBox()
    self.per_day_spin.setRange(1, 50)
    self.per_day_spin.setValue(max(1, min(total_videos, 5)))
    row("Vídeos por dia", self.per_day_spin)

    self.start_combo = QComboBox()
    self.start_combo.addItems([f"{h:02d}:00" for h in range(24)])
    self.start_combo.setCurrentText("09:00")
    self.end_combo = QComboBox()
    self.end_combo.addItems([f"{h:02d}:00" for h in range(24)])
    self.end_combo.setCurrentText("21:00")
    row("Janela diária", self.start_combo, self.end_combo)

    self.interval_spin = QSpinBox()
    self.interval_spin.setRange(15, 360)
    self.interval_spin.setSingleStep(5)
    self.interval_spin.setValue(60)
    self.interval_spin.setSuffix(" min")
    row("Intervalo entre posts", self.interval_spin)

    ok = QLabel("✓ Horários sempre em passos de 5 minutos")
    ok.setStyleSheet(f"color: {TT_GREEN}; font-size: 12px;")
    lay.addWidget(ok)

    btns = QHBoxLayout()
    btns.addStretch(1)
    cancel = QPushButton("Cancelar")
    cancel.setObjectName("ttSecondary")
    cancel.clicked.connect(self.reject)
    btns.addWidget(cancel)
    apply_btn = QPushButton("Aplicar")
    apply_btn.setObjectName("ttPrimary")
    apply_btn.clicked.connect(self._on_apply)
    btns.addWidget(apply_btn)
    lay.addLayout(btns)

  def _on_apply(self) -> None:
    self.applied.emit(
      self.per_day_spin.value(),
      self.start_combo.currentText(),
      self.end_combo.currentText(),
      self.interval_spin.value(),
    )
    self.accept()


class ScheduleApprovalDialog(QDialog):
  """Dialog prompting the user to approve recalculated schedule slots before execution."""

  def __init__(
    self,
    recalculated_items: list[dict[str, Any]],
    parent: QWidget | None = None,
  ) -> None:
    super().__init__(parent)
    self.setWindowTitle("Ajuste Inteligente de Horários da Fila")
    self.setModal(True)
    self.resize(880, 500)
    self.setStyleSheet(_dialog_style() + f"""
      QTableWidget {{ background: #FFFFFF; border: 1px solid {TT_BORDER}; border-radius: 6px;
        gridline-color: transparent; color: {TT_TEXT}; }}
      QTableWidget::item {{ border-bottom: 1px solid #F1F1F2; padding: 6px; }}
      QHeaderView::section {{ background: #FFFFFF; color: {TT_TEXT_2}; font-weight: 600; border: none;
        border-bottom: 1px solid {TT_BORDER}; padding: 8px 6px; }}
    """)

    lay = QVBoxLayout(self)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(12)

    lay.addWidget(_title("Ajuste Obrigatório de Horários da Fila"))

    desc = QLabel(
      "Identificamos que alguns vídeos possuem horários vencidos, com antecedência insuficiente "
      "(< 25 min), duplicados ou acima do limite de 10 dias do TikTok.<br>"
      "Para evitar que o TikTok bloqueie a publicação, calculamos uma <b>nova grade sequencial válida</b>:"
    )
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 13px; line-height: 1.4;")
    lay.addWidget(desc)

    self.table = QTableWidget(len(recalculated_items), 5)
    self.table.setHorizontalHeaderLabels([
      "#", "Arquivo", "Horário Anterior", "Novo Horário Proposto", "Motivo do Ajuste"
    ])
    self.table.verticalHeader().setVisible(False)
    self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    self.table.setShowGrid(False)

    hh = self.table.horizontalHeader()
    hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    for r, it in enumerate(recalculated_items):
      old_dt = it.get("old_schedule")
      new_dt = it.get("new_schedule")
      changed = bool(it.get("changed", False))

      old_str = old_dt.strftime("%d/%m/%Y %H:%M") if isinstance(old_dt, datetime) else "Imediato"
      new_str = new_dt.strftime("%d/%m/%Y %H:%M") if isinstance(new_dt, datetime) else "Imediato"
      reason = str(it.get("reason", "Ajustado"))

      cells = [
        str(r + 1),
        str(it.get("filename", "")),
        old_str,
        new_str,
        reason,
      ]
      for c, txt in enumerate(cells):
        item = QTableWidgetItem(txt)
        item.setToolTip(txt)
        if c == 2 and changed:
          item.setForeground(Qt.GlobalColor.red)
        elif c == 3 and changed:
          item.setForeground(Qt.GlobalColor.darkGreen)
          font = item.font()
          font.setBold(True)
          item.setFont(font)
        self.table.setItem(r, c, item)
      self.table.setRowHeight(r, 34)

    lay.addWidget(self.table, 1)

    note = QLabel(
      "✓ Nenhum navegador será aberto sem a sua autorização. "
      "Ao aprovar, a tabela e as tarefas serão atualizadas com os novos horários."
    )
    note.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 12px;")
    lay.addWidget(note)

    lay.addWidget(hline())

    btns = QHBoxLayout()
    btns.addStretch(1)

    cancel_btn = QPushButton("Cancelar / Revisar Manualmente")
    cancel_btn.setObjectName("ttSecondary")
    cancel_btn.clicked.connect(self.reject)
    btns.addWidget(cancel_btn)

    approve_btn = QPushButton("Aprovar Novos Horários e Executar")
    approve_btn.setObjectName("ttPrimary")
    approve_btn.clicked.connect(self.accept)
    btns.addWidget(approve_btn)

    lay.addLayout(btns)
