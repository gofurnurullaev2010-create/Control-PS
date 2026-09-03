"""Qa\'rejetler sahifasi — joriy kassa + 1 oylik kunlik tarix."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
from app.ui.dialogs.colors import BG_CARD, BG_HEADER, BORDER_COLOR, COL_RED, TEXT_PRIMARY, TEXT_SECONDARY
from app.ui.dialogs.finance_dialogs import ExpenseAddDialog, ExpenseEditDialog
_CURRENT = '__current__'
def _fmt_money(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
def _split_dt(value: str) -> tuple[str, str]:
    text = (value or '').strip()
    if not text:
        return ('—', '')
    else:
        if 'T' in text:
            d, t = text.split('T', 1)
            return (d.replace('-', '.'), t[:8])
        else:
            if ' ' in text:
                parts = text.split()
                return (parts[0], parts[1][:8] if len(parts) > 1 else '')
            else:
                try:
                    dt = datetime.fromisoformat(text)
                    return (dt.strftime('%d.%m.%Y'), dt.strftime('%H:%M:%S'))
                except ValueError:
                    return (text, '')
def _wallet_label(wallet: str) -> str:
    w = (wallet or '').strip().lower()
    if w in ['safe', 'ceyf', 'сейф']:
        return 'Ceyf puli'
    else:
        return 'Kassa puli'
class ExpensesPage(QWidget):
    """Chapda tarix (1 oy), o\'rtada jadval. Joriy kassa jabıwdan keyin bo\'shaydi."""
    def __init__(self, parent=None, on_changed: Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._search = ''
        self._mode = _CURRENT
        self._rows = []
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        left = QVBoxLayout()
        left.setSpacing(6)
        hist_cap = QLabel('Tarix (1 oy)')
        hist_cap.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px; font-weight: 800;')
        left.addWidget(hist_cap)
        self.days = QListWidget()
        self.days.setFixedWidth(168)
        self.days.setStyleSheet(f'\n            QListWidget {{\n                background: {BG_CARD}; border: 1px solid {BORDER_COLOR};\n                border-radius: 10px; color: {TEXT_PRIMARY}; font-size: 12px;\n            }}\n            QListWidget::item {{ padding: 10px 8px; border-bottom: 1px solid {BORDER_COLOR}; }}\n            QListWidget::item:selected {{ background: #EEF2FF; color: {TEXT_PRIMARY}; font-weight: 800; }}\n            ')
        self.days.itemClicked.connect(self._on_day_clicked)
        left.addWidget(self.days, 1)
        root.addLayout(left)
        mid = QVBoxLayout()
        mid.setSpacing(6)
        title_row = QHBoxLayout()
        self._title = QLabel('Joriy kassa')
        self._title.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 800;')
        title_row.addWidget(self._title, 1)
        self._btn_edit = QPushButton('O\'zgartiriw')
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.setToolTip('Tanlangan qatorning nomi va summasini o\'zgartirish')
        self._btn_edit.setStyleSheet(f'\n            QPushButton {{\n                background: {BG_HEADER}; color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER_COLOR}; border-radius: 8px;\n                padding: 8px 14px; font-weight: 800;\n            }}\n            QPushButton:hover {{ border: 1px solid {COL_RED}; }}\n            ')
        self._btn_edit.clicked.connect(self.edit_selected)
        title_row.addWidget(self._btn_edit)
        mid.addLayout(title_row)
        hint = QLabel('Qatorni ikki marta bosing yoki «O\'zgartiriw» — atı va swmması.')
        hint.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px; font-weight: 600;')
        mid.addWidget(hint)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Qa\'rejet turi', 'Summa', 'Pul deregi', 'Sipatlama', 'Waqti'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(f'\n            QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 10px; }}\n            QHeaderView::section {{\n                background: {BG_HEADER}; padding: 8px; border: none;\n                border-bottom: 1px solid {BORDER_COLOR}; font-weight: 800;\n            }}\n            QTableWidget::item:selected {{ background: #E8EDF5; color: {TEXT_PRIMARY}; }}\n            ')
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        mid.addWidget(self.table, 1)
        root.addLayout(mid, 1)
        self.reload()
    def set_search(self, text: str) -> None:
        self._search = (text or '').strip()
        self._reload_table()
    def reload(self) -> None:
        self._reload_days()
        self._reload_table()
    def add_expense(self) -> None:
        dlg = ExpenseAddDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            etype, amount, wallet, note = dlg.values()
            try:
                db.add_expense(etype, amount, wallet, note)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
                return None
            self._mode = _CURRENT
            self.reload()
            if self._on_changed:
                self._on_changed()
    def edit_selected(self) -> None:
        row = self.table.currentRow()
        self._edit_row(row)
    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        self._edit_row(row)
    def _edit_row(self, row: int) -> None:
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, 'Qa\'rejetler', 'Avval ro\'yxatdan qator tanlan\'.')
            return
        rec = self._rows[row]
        if not rec.get('id'):
            QMessageBox.warning(self, 'Xatolik', 'Bu qatorni o\'zgartirib bo\'lmaydi.')
            return
        dlg = ExpenseEditDialog(rec, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        etype, amount = dlg.values()
        try:
            db.update_expense(int(rec['id']), etype, amount)
            if str(rec.get('expense_type') or '') != etype:
                db.remember_expense_custom_type(etype)
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
            return
        self.reload()
        if self._on_changed:
            self._on_changed()
    def _reload_days(self) -> None:
        self.days.blockSignals(True)
        self.days.clear()
        try:
            current = db.list_current_period_expenses('')
            cur_total = sum((float(r.get('amount') or 0) for r in current if str(r.get('wallet') or 'cash').strip().lower() not in ['safe', 'ceyf', 'сейф']))
        except Exception:
            cur_total = 0.0
        cur_item = QListWidgetItem(f'Joriy kassa\n{_fmt_money(cur_total)}')
        cur_item.setData(Qt.ItemDataRole.UserRole, _CURRENT)
        self.days.addItem(cur_item)
        try:
            summary = db.expense_day_summary(30)
        except Exception:
            summary = []
        for row in summary:
            day = str(row.get('day') or '')
            total = float(row.get('total', 0) or 0)
            item = QListWidgetItem(f'{day}\n{_fmt_money(total)}')
            item.setData(Qt.ItemDataRole.UserRole, day)
            self.days.addItem(item)
        select_row = 0
        for i in range(self.days.count()):
            if self.days.item(i).data(Qt.ItemDataRole.UserRole) == self._mode:
                select_row = i
                break
        else:
            self._mode = _CURRENT
            select_row = 0
        self.days.setCurrentRow(select_row)
        self.days.blockSignals(False)
    def _on_day_clicked(self, item: QListWidgetItem) -> None:
        role = item.data(Qt.ItemDataRole.UserRole)
        self._mode = _CURRENT if role in (None, _CURRENT) else str(role)
        self._reload_table()
    def _reload_table(self) -> None:
        search = self._search
        try:
            if self._mode == _CURRENT:
                rows = db.list_current_period_expenses(search)
                self._title.setText('Joriy kassa (jabıwdan keyin tozalanadi)')
            else:
                rows = db.list_expenses(search, day=self._mode, keep_days=30)
                self._title.setText(f'Tarix: {self._mode}')
        except Exception:
            rows = []
        self._rows = rows
        self.table.setRowCount(len(rows))
        self.table.verticalHeader().setDefaultSectionSize(44)
        for i, r in enumerate(rows):
            type_item = QTableWidgetItem(str(r.get('expense_type') or ''))
            type_item.setData(Qt.ItemDataRole.UserRole, int(r.get('id') or 0))
            amount_item = QTableWidgetItem(_fmt_money(float(r.get('amount') or 0)))
            amount_item.setForeground(QColor(COL_RED))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            wallet_item = QTableWidgetItem(_wallet_label(str(r.get('wallet') or '')))
            note_item = QTableWidgetItem(str(r.get('note') or ''))
            d, t = _split_dt(str(r.get('created_time') or ''))
            time_item = QTableWidgetItem(f'{d}\n{t}' if t else d)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, type_item)
            self.table.setItem(i, 1, amount_item)
            self.table.setItem(i, 2, wallet_item)
            self.table.setItem(i, 3, note_item)
            self.table.setItem(i, 4, time_item)
            self.table.setRowHeight(i, 44)
    def row_count(self) -> int:
        return self.table.rowCount()
