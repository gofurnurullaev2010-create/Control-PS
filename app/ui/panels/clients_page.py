"""Klientler sahifasi — ro\'yxat + o\'ngda Klient mag\'liwmati."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
from app.ui.dialogs.colors import BG_CARD, BG_HEADER, BORDER_COLOR, COL_RED, TEXT_PRIMARY, TEXT_SECONDARY
from app.ui.theme import ACCENT, ACCENT_HOVER
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
def _fmt_dt_long(value: str) -> str:
    d, t = _split_dt(value)
    if d and t:
        return f'{d}  {t}'
    else:
        return d or '—'
def _fmt_dt_short(value: str) -> str:
    d, _ = _split_dt(value)
    return d or '—'
def list_clients_aggregated(search: str='') -> list[dict[str, Any]]:
    """Klientlar: qarzdorlar + bronlar bo\'yicha guruhlangan."""
    q = (search or '').strip().lower()
    clients = {}
    def _key(name: str, phone: str) -> tuple[str, str]:
        return ((name or '').strip(), (phone or '').strip())
    def _touch(name: str, phone: str, when: str='') -> dict[str, Any]:
        key = _key(name, phone)
        if not key[0] and (not key[1]):
            return {}
        else:
            item = clients.setdefault(key, {'name': key[0], 'phone': key[1], 'debt': 0.0, 'created': when or '', 'debts': []})
            if when:
                if not item['created'] or str(when) < str(item['created']):
                    item['created'] = when
            return item
    try:
        for r in db.list_debtors('', include_paid=True):
            name = str(r.get('client_name') or '')
            phone = str(r.get('phone') or '')
            item = _touch(name, phone, str(r.get('debt_time') or ''))
            if not item:
                continue
            else:
                if not r.get('paid'):
                    amt = float(r.get('amount') or 0)
                    item['debt'] = float(item.get('debt') or 0) + amt
                    item['debts'].append(dict(r))
    except Exception:
        pass
    try:
        for r in db.list_bookings('', include_closed=True):
            _touch(str(r.get('client_name') or ''), str(r.get('phone') or ''), str(r.get('booking_time') or r.get('created_time') or ''))
    except Exception:
        pass
    rows = list(clients.values())
    if q:
        rows = [c for c in rows if q in str(c.get('name') or '').lower() or q in str(c.get('phone') or '').lower()]
    rows.sort(key=lambda c: str(c.get('created') or ''), reverse=True)
    return rows
class ClientsPage(QWidget):
    """Chapda klientlar jadvali, o\'ngda Klient mag\'liwmati."""
    def __init__(self, parent=None, on_changed: Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._search = ''
        self._rows = []
        self._current = None
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(0)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['№', 'Ati', 'Telefoni', 'Ja\'mi qarzi', 'Jaratilg\'an waqti'])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f'\n            QTableWidget {{\n                background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 10px;\n                gridline-color: {BORDER_COLOR}; font-size: 13px;\n            }}\n            QHeaderView::section {{\n                background: {BG_HEADER}; padding: 10px 8px; border: none;\n                border-bottom: 1px solid {BORDER_COLOR}; font-weight: 800;\n            }}\n            QTableWidget::item:selected {{ background: #E8EDF5; color: {TEXT_PRIMARY}; }}\n            ')
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        left.addWidget(self.table)
        root.addLayout(left, 1)
        self._detail = QFrame()
        self._detail.setObjectName('ClientDetail')
        self._detail.setMinimumWidth(360)
        self._detail.setMaximumWidth(420)
        self._detail.setStyleSheet(f'\n            QFrame#ClientDetail {{\n                background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 12px;\n            }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            ')
        dlay = QVBoxLayout(self._detail)
        dlay.setContentsMargins(16, 14, 16, 14)
        dlay.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel('Klient mag\'liwmati')
        title.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 800;')
        head.addWidget(title, 1)
        self._btn_edit = QPushButton('O\'zgertiw')
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.setFlat(True)
        self._btn_edit.setStyleSheet('color: #2563EB; font-weight: 800;')
        self._btn_edit.clicked.connect(self._edit_client)
        head.addWidget(self._btn_edit)
        dlay.addLayout(head)
        self._empty = QLabel('Klientni tanlang')
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px; padding: 40px;')
        dlay.addWidget(self._empty)
        self._body = QWidget()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)
        self._c_name = QLabel('—')
        self._c_name.setFont(QFont('Segoe UI', 20, QFont.Weight.Bold))
        self._c_name.setWordWrap(True)
        body.addWidget(self._c_name)
        self._btn_pay = QPushButton('💵  Qarizdi to\'lew')
        self._btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pay.setStyleSheet('QPushButton { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 22px; padding: 10px 14px; font-weight: 800; text-align: left; }QPushButton:hover { background: #E8EAED; }')
        self._btn_pay.clicked.connect(self._pay_debt)
        body.addWidget(self._btn_pay)
        info = QFrame()
        info.setStyleSheet(f'QFrame {{ background: #F8FAFC; border: 1px solid {BORDER_COLOR}; border-radius: 10px; }}')
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(12, 10, 12, 10)
        info_lay.setSpacing(6)
        self._c_phone = QLabel('Telefoni: —')
        self._c_created = QLabel('Jaratilg\'an waqti: —')
        self._c_debt_lbl = QLabel('Ja\'mi qarzi')
        self._c_debt_lbl.setStyleSheet('font-weight: 800; margin-top: 4px;')
        self._c_total = QLabel('0')
        self._c_total.setStyleSheet(f'color: {COL_RED}; font-size: 24px; font-weight: 900;')
        for w in [self._c_phone, self._c_created]:
            w.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
            info_lay.addWidget(w)
        info_lay.addWidget(self._c_debt_lbl)
        info_lay.addWidget(self._c_total)
        body.addWidget(info)
        debts_head = QHBoxLayout()
        self._c_debts_title = QLabel('Qarizlari')
        self._c_debts_title.setStyleSheet('font-weight: 800; font-size: 14px;')
        debts_head.addWidget(self._c_debts_title, 1)
        self._c_debts_badge = QLabel('0')
        self._c_debts_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._c_debts_badge.setFixedHeight(22)
        self._c_debts_badge.setMinimumWidth(28)
        self._c_debts_badge.setStyleSheet('background: #EEF2FF; color: #3730A3; border-radius: 11px; padding: 2px 8px; font-weight: 800; font-size: 12px;')
        debts_head.addWidget(self._c_debts_badge)
        body.addLayout(debts_head)
        self._c_table = QTableWidget()
        self._c_table.setColumnCount(4)
        self._c_table.setHorizontalHeaderLabels(['№', 'Qariz mug\'dari', 'Qariz waqti', 'Jazg\'an'])
        self._c_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._c_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._c_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._c_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._c_table.verticalHeader().setVisible(False)
        self._c_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._c_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._c_table.setStyleSheet(f'\n            QTableWidget {{ border: 1px solid {BORDER_COLOR}; border-radius: 8px; }}\n            QHeaderView::section {{\n                background: {BG_HEADER}; padding: 6px; border: none;\n                border-bottom: 1px solid {BORDER_COLOR}; font-weight: 700; font-size: 11px;\n            }}\n            ')
        body.addWidget(self._c_table, 1)
        dlay.addWidget(self._body, 1)
        self._body.hide()
        root.addWidget(self._detail)
        self.reload()
    def set_search(self, text: str) -> None:
        self._search = (text or '').strip()
        self.reload()
    def reload(self) -> None:
        prev = None
        if self._current:
            prev = (self._current.get('name'), self._current.get('phone'))
        self._rows = list_clients_aggregated(self._search)
        self.table.setRowCount(len(self._rows))
        self.table.verticalHeader().setDefaultSectionSize(44)
        select_row = (-1)
        for i, c in enumerate(self._rows):
            no = QTableWidgetItem(str(i + 1))
            no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name = QTableWidgetItem(str(c.get('name') or '—'))
            phone = QTableWidgetItem(str(c.get('phone') or '—'))
            debt = float(c.get('debt') or 0)
            debt_item = QTableWidgetItem(_fmt_money(debt))
            debt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if debt > 0:
                debt_item.setForeground(QColor(COL_RED))
            when = QTableWidgetItem(_fmt_dt_short(str(c.get('created') or '')))
            when.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, no)
            self.table.setItem(i, 1, name)
            self.table.setItem(i, 2, phone)
            self.table.setItem(i, 3, debt_item)
            self.table.setItem(i, 4, when)
            if prev and (c.get('name'), c.get('phone')) == prev:
                    select_row = i
        if select_row >= 0:
            self.table.selectRow(select_row)
            self._show_detail(self._rows[select_row])
        else:
            if self._rows:
                self.table.clearSelection()
                self._show_empty()
            else:
                self._show_empty()
    def add_client(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle('Yangi klient')
        dlg.setMinimumWidth(360)
        form = QFormLayout(dlg)
        name_ed = QLineEdit()
        phone_ed = QLineEdit()
        phone_ed.setPlaceholderText('+998...')
        form.addRow('Ati *', name_ed)
        form.addRow('Telefoni', phone_ed)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            name = name_ed.text().strip()
            phone = phone_ed.text().strip()
            if not name:
                QMessageBox.warning(self, 'Klient', 'Ismni kiriting.')
                return
            else:
                try:
                    self._ensure_client_record(name, phone)
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', str(e))
                    return None
                self.reload()
                if self._on_changed:
                    self._on_changed()
    @staticmethod
    def _ensure_client_record(name: str, phone: str) -> None:
        """Klientni ro\'yxatga olish (qarzsiz) — bookings jadvaliga yengil belgi."""
        for c in list_clients_aggregated(''):
            if str(c.get('name') or '') == name and str(c.get('phone') or '') == phone:
                    return
        conn = db._connect()
        now = datetime.now().isoformat(timespec='seconds')
        conn.execute('\n            INSERT INTO debtors (client_name, phone, amount, debt_time, note, paid, paid_time)\n            VALUES (?, ?, 0, ?, \'klient_royxat\', 1, ?)\n            ', (name, phone, now, now))
        conn.commit()
        conn.close()
    def _on_row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        else:
            idx = rows[0].row()
            if idx < 0 or idx >= len(self._rows):
                return None
            else:
                self._show_detail(self._rows[idx])
    def _show_empty(self) -> None:
        self._current = None
        self._empty.show()
        self._body.hide()
    def _show_detail(self, c: dict[str, Any]) -> None:
        self._current = c
        self._empty.hide()
        self._body.show()
        name = str(c.get('name') or '—')
        phone = str(c.get('phone') or '')
        self._c_name.setText(name)
        self._c_phone.setText(f"Telefoni: {phone or '—'}")
        self._c_created.setText(f"Jaratilg\'an waqti: {_fmt_dt_long(str(c.get('created') or ''))}")
        debt = float(c.get('debt') or 0)
        self._c_total.setText(_fmt_money(debt))
        debts = list(c.get('debts') or [])
        if not debts and name:
                debts = [r for r in db.list_debtors('', include_paid=False) if str(r.get('client_name') or '') == name and str(r.get('phone') or '') == phone]
        self._c_debts_badge.setText(str(len(debts)))
        self._c_debts_title.setText('Qarizlari')
        self._btn_pay.setEnabled(debt > 0)
        debts_sorted = sorted(debts, key=lambda r: str(r.get('debt_time') or ''), reverse=True)
        self._c_table.setRowCount(len(debts_sorted))
        for i, r in enumerate(debts_sorted):
            no = QTableWidgetItem(str(len(debts_sorted) - i))
            no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            amt = QTableWidgetItem(_fmt_money(float(r.get('amount') or 0)))
            amt.setForeground(QColor(COL_RED))
            amt.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            d, t = _split_dt(str(r.get('debt_time') or ''))
            when = QTableWidgetItem(f'{d}  {t}' if t else d)
            who = QTableWidgetItem('Kompyuter')
            self._c_table.setItem(i, 0, no)
            self._c_table.setItem(i, 1, amt)
            self._c_table.setItem(i, 2, when)
            self._c_table.setItem(i, 3, who)
            self._c_table.setRowHeight(i, 40)
    def _edit_client(self) -> None:
        if not self._current:
            return
        else:
            old_name = str(self._current.get('name') or '')
            old_phone = str(self._current.get('phone') or '')
            dlg = QDialog(self)
            dlg.setWindowTitle('Klientni o\'zgertiw')
            dlg.setMinimumWidth(360)
            form = QFormLayout(dlg)
            name_ed = QLineEdit(old_name)
            phone_ed = QLineEdit(old_phone)
            form.addRow('Ati', name_ed)
            form.addRow('Telefoni', phone_ed)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            form.addRow(buttons)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            else:
                new_name = name_ed.text().strip()
                new_phone = phone_ed.text().strip()
                if not new_name:
                    QMessageBox.warning(self, 'Klient', 'Ism bo\'sh bo\'lmasin.')
                    return
                else:
                    try:
                        conn = db._connect()
                        conn.execute('UPDATE debtors SET client_name = ?, phone = ? WHERE client_name = ? AND phone = ?', (new_name, new_phone, old_name, old_phone))
                        conn.execute('UPDATE debt_payment_events SET client_name = ?, phone = ? WHERE client_name = ? AND phone = ?', (new_name, new_phone, old_name, old_phone))
                        try:
                            conn.execute('UPDATE bookings SET client_name = ?, phone = ? WHERE client_name = ? AND phone = ?', (new_name, new_phone, old_name, old_phone))
                        except Exception:
                            pass
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        QMessageBox.critical(self, 'Xatolik', str(e))
                        return None
                    self.reload()
                    if self._on_changed:
                        self._on_changed()
    def _pay_debt(self) -> None:
        if not self._current:
            return
        else:
            name = str(self._current.get('name') or '')
            phone = str(self._current.get('phone') or '')
            open_rows = [r for r in db.list_debtors('', include_paid=False) if str(r.get('client_name') or '') == name and str(r.get('phone') or '') == phone]
            total = sum((float(r.get('amount') or 0) for r in open_rows))
            if total <= 0:
                QMessageBox.information(self, 'Qariz', 'Ochiq qariz yo\'q.')
                return
            else:
                dlg = QDialog(self)
                dlg.setWindowTitle('Qarizdi to\'lew')
                dlg.setMinimumWidth(360)
                form = QFormLayout(dlg)
                info = QLabel(f'{name}\nJami qariz: {_fmt_money(total)} so\'m')
                info.setStyleSheet('font-weight: 800; font-size: 14px;')
                form.addRow(info)
                spin = QDoubleSpinBox()
                spin.setRange(0, total)
                spin.setDecimals(0)
                spin.setSingleStep(1000)
                spin.setGroupSeparatorShown(True)
                spin.setValue(total)
                spin.setSuffix(' so\'m')
                form.addRow('To\'lov summasi', spin)
                buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                buttons.button(QDialogButtonBox.StandardButton.Ok).setText('To\'lew')
                buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(f'background:{ACCENT}; color:#FFF; font-weight:800; padding:8px 16px; border:none; border-radius:8px;')
                buttons.accepted.connect(dlg.accept)
                buttons.rejected.connect(dlg.reject)
                form.addRow(buttons)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                else:
                    try:
                        db.pay_client_debts(name, phone, float(spin.value()))
                    except Exception as e:
                        QMessageBox.critical(self, 'Xatolik', str(e))
                        return None
                    self.reload()
                    if self._on_changed:
                        self._on_changed()