"""Qarizdarlar sahifasi — kunlar | jadval | Qariz/Klient mag\'liwmati."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
from app.ui.dialogs.colors import BG_CARD, BG_HEADER, BORDER_COLOR, COL_RED, TEXT_PRIMARY, TEXT_SECONDARY
from app.ui.dialogs.finance_dialogs import DebtorAddDialog
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
class DebtorsPage(QWidget):
    """3 panel: kunlar, qarzdorlar jadvali, o\'ngda Qariz yoki Klient mag\'liwmati."""
    def __init__(self, parent=None, on_changed: Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._selected_day = None
        self._rows = []
        self._current = None
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        self.days = QListWidget()
        self.days.setFixedWidth(168)
        self.days.setStyleSheet(f'\n            QListWidget {{\n                background: {BG_CARD}; border: 1px solid {BORDER_COLOR};\n                border-radius: 10px; color: {TEXT_PRIMARY}; font-size: 12px;\n            }}\n            QListWidget::item {{ padding: 10px 8px; border-bottom: 1px solid {BORDER_COLOR}; }}\n            QListWidget::item:selected {{ background: #EEF2FF; color: {TEXT_PRIMARY}; font-weight: 800; }}\n            ')
        self.days.itemClicked.connect(self._on_day_clicked)
        root.addWidget(self.days)
        mid = QVBoxLayout()
        mid.setSpacing(0)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['Klient', 'Qariz mug\'dari', 'Qariz waqti'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(f'\n            QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 10px; }}\n            QHeaderView::section {{\n                background: {BG_HEADER}; padding: 8px; border: none;\n                border-bottom: 1px solid {BORDER_COLOR}; font-weight: 800;\n            }}\n            QTableWidget::item:selected {{ background: #E8EDF5; color: {TEXT_PRIMARY}; }}\n            ')
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        mid.addWidget(self.table)
        root.addLayout(mid, 1)
        self.detail_stack = QStackedWidget()
        self.detail_stack.setFixedWidth(340)
        self._empty_panel = self._make_empty_panel()
        self._debt_panel = self._make_debt_panel()
        self._client_panel = self._make_client_panel()
        self.detail_stack.addWidget(self._empty_panel)
        self.detail_stack.addWidget(self._debt_panel)
        self.detail_stack.addWidget(self._client_panel)
        root.addWidget(self.detail_stack)
        self.reload()
    def _make_empty_panel(self) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 12px; }}')
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel('Klientni tanlang')
        lbl.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px;')
        lay.addWidget(lbl)
        return w
    def _make_debt_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName('DebtDetail')
        w.setStyleSheet(f'\n            QFrame#DebtDetail {{\n                background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 12px;\n            }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            ')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        self._d_title = QLabel('—')
        self._d_title.setWordWrap(True)
        self._d_title.setFont(QFont('Segoe UI', 14, QFont.Weight.Bold))
        head.addWidget(self._d_title, 1)
        self._btn_see_all = QPushButton('BARLIG\'IN KO\'RIW')
        self._btn_see_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_see_all.setFlat(True)
        self._btn_see_all.setStyleSheet('color: #2563EB; font-weight: 800; text-decoration: underline;')
        self._btn_see_all.clicked.connect(self._show_client_view)
        head.addWidget(self._btn_see_all)
        lay.addLayout(head)
        cap = QLabel('Qariz mag\'liwmati')
        cap.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 700;')
        lay.addWidget(cap)
        self._d_amount = QLabel('0')
        self._d_amount.setStyleSheet(f'color: {COL_RED}; font-size: 28px; font-weight: 900;')
        lay.addWidget(self._d_amount)
        self._d_when = QLabel('—')
        self._d_when.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
        lay.addWidget(self._d_when)
        hist = QLabel('O\'zgerisler Tariyxi')
        hist.setStyleSheet('font-size: 13px; font-weight: 800; margin-top: 8px;')
        lay.addWidget(hist)
        self._hist_box = QVBoxLayout()
        self._hist_box.setSpacing(8)
        lay.addLayout(self._hist_box)
        lay.addStretch(1)
        pay = QPushButton('✓  To\'landi')
        pay.setStyleSheet('QPushButton { background: #16A34A; color: white; font-weight: 900; border: none; border-radius: 8px; padding: 10px; }')
        pay.clicked.connect(self._mark_current_paid)
        lay.addWidget(pay)
        return w
    def _make_client_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName('ClientDetail')
        w.setStyleSheet(f'\n            QFrame#ClientDetail {{\n                background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 12px;\n            }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            ')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        self._c_name = QLabel('—')
        self._c_name.setFont(QFont('Segoe UI', 18, QFont.Weight.Bold))
        head.addWidget(self._c_name, 1)
        back = QPushButton('← Qariz')
        back.setFlat(True)
        back.setStyleSheet('color: #2563EB; font-weight: 800;')
        back.clicked.connect(self._show_debt_view)
        head.addWidget(back)
        lay.addLayout(head)
        sub = QLabel('Klient mag\'liwmati')
        sub.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 700;')
        lay.addWidget(sub)
        pay = QPushButton('💵  Qarizdi to\'lew')
        pay.setStyleSheet('QPushButton { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 20px; padding: 10px 14px; font-weight: 800; }')
        pay.clicked.connect(self._pay_via_adjust)
        lay.addWidget(pay)
        self._c_phone = QLabel('Telefoni: —')
        self._c_created = QLabel('Jaratilg\'an waqti: —')
        self._c_total = QLabel('0')
        self._c_total.setStyleSheet(f'color: {COL_RED}; font-size: 26px; font-weight: 900;')
        for wdg in [self._c_phone, self._c_created]:
            wdg.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
            lay.addWidget(wdg)
        tot_lbl = QLabel('Ja\'mi qarzi')
        tot_lbl.setStyleSheet('font-weight: 800;')
        lay.addWidget(tot_lbl)
        lay.addWidget(self._c_total)
        self._c_debts_title = QLabel('Qarizlari (0)')
        self._c_debts_title.setStyleSheet('font-weight: 800; margin-top: 6px;')
        lay.addWidget(self._c_debts_title)
        self._c_table = QTableWidget()
        self._c_table.setColumnCount(3)
        self._c_table.setHorizontalHeaderLabels(['No', 'Mug\'dari', 'Waqti'])
        self._c_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._c_table.verticalHeader().setVisible(False)
        self._c_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._c_table.setMaximumHeight(280)
        lay.addWidget(self._c_table, 1)
        return w
    def set_search(self, text: str) -> None:
        self._search = (text or '').strip()
        self._reload_table()
    def reload(self) -> None:
        self._search = getattr(self, '_search', '')
        self._reload_days()
        self._reload_table()
    def add_debtor(self) -> None:
        dlg = DebtorAddDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            try:
                db.add_debtor(dlg.name.text(), dlg.phone.text(), dlg.amount.value(), dlg.note.text())
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
                return None
            self._selected_day = None
            self.reload()
            if self._on_changed:
                self._on_changed()
    def _reload_days(self) -> None:
        self.days.blockSignals(True)
        self.days.clear()
        summary = db.debtor_day_summary()
        total_all = sum((float(r.get('total', 0) or 0) for r in summary))
        all_item = QListWidgetItem(f'Barlig\'i\n{_fmt_money(total_all)}')
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.days.addItem(all_item)
        for row in summary:
            day = str(row.get('day') or '')
            total = float(row.get('total', 0) or 0)
            item = QListWidgetItem(f'{day}\n{_fmt_money(total)}')
            item.setData(Qt.ItemDataRole.UserRole, day)
            self.days.addItem(item)
        self.days.setCurrentRow(0)
        self.days.blockSignals(False)
        self._selected_day = None
    def _on_day_clicked(self, item: QListWidgetItem) -> None:
        self._selected_day = item.data(Qt.ItemDataRole.UserRole)
        self._reload_table()
    def _reload_table(self) -> None:
        rows = db.list_debtors(getattr(self, '_search', ''), self._selected_day)
        self._rows = rows
        self.table.setRowCount(len(rows))
        self.table.verticalHeader().setDefaultSectionSize(48)
        for i, r in enumerate(rows):
            name = str(r.get('client_name', '') or '')
            phone = str(r.get('phone', '') or '')
            label = f'{name} - {phone}' if phone else name
            name_item = QTableWidgetItem(label)
            amount_item = QTableWidgetItem(_fmt_money(float(r.get('amount', 0) or 0)))
            amount_item.setForeground(QColor(COL_RED))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            d, t = _split_dt(str(r.get('debt_time', '') or ''))
            time_item = QTableWidgetItem(f'{d}\n{t}' if t else d)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, amount_item)
            self.table.setItem(i, 2, time_item)
            self.table.setRowHeight(i, 48)
        if not rows:
            self._current = None
            self.detail_stack.setCurrentIndex(0)
    def _on_row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        else:
            idx = rows[0].row()
            if idx < 0 or idx >= len(self._rows):
                return None
            else:
                self._current = self._rows[idx]
                self._fill_debt_panel(self._current)
                self.detail_stack.setCurrentIndex(1)
    def _fill_debt_panel(self, r: dict[str, Any]) -> None:
        name = str(r.get('client_name', '') or '')
        phone = str(r.get('phone', '') or '')
        self._d_title.setText(f'{name} - {phone}' if phone else name)
        self._d_amount.setText(_fmt_money(float(r.get('amount', 0) or 0)))
        self._d_when.setText(f"Qariz waqti: {_fmt_dt_long(str(r.get('debt_time', '') or ''))}")
        while self._hist_box.count():
            item = self._hist_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        created = str(r.get('debt_time', '') or '')
        for label, value, two_line in [('Jaratilg\'an waqti', created, True), ('Jaratqan adam', 'Kompyuter', False), ('Son\'g\'i o\'zgertilgen', created, True), ('Son\'g\'i o\'zgertken', 'Kompyuter', False)]:
            row = QHBoxLayout()
            cap = QLabel(label)
            cap.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
            row.addWidget(cap, 1)
            if two_line:
                d, t = _split_dt(value)
                box = QVBoxLayout()
                box.setSpacing(0)
                ld = QLabel(d)
                ld.setStyleSheet('color: #2563EB; font-weight: 800; font-size: 14px;')
                lt = QLabel(t)
                lt.setStyleSheet('color: #2563EB; font-weight: 700; font-size: 13px;')
                box.addWidget(ld)
                box.addWidget(lt)
                wrap = QWidget()
                wrap.setLayout(box)
                row.addWidget(wrap)
            else:
                val = QLabel(value)
                val.setStyleSheet('color: #2563EB; font-weight: 800; font-size: 14px;')
                row.addWidget(val)
            host = QWidget()
            host.setLayout(row)
            self._hist_box.addWidget(host)
    def _show_debt_view(self) -> None:
        if self._current:
            self._fill_debt_panel(self._current)
            self.detail_stack.setCurrentIndex(1)
    def _show_client_view(self) -> None:
        if not self._current:
            return
        else:
            name = str(self._current.get('client_name', '') or '')
            phone = str(self._current.get('phone', '') or '')
            all_rows = [r for r in db.list_debtors('', include_paid=False) if str(r.get('client_name') or '') == name and str(r.get('phone') or '') == phone]
            if not all_rows:
                all_rows = [self._current]
            self._c_name.setText(name or '—')
            self._c_phone.setText(f"Telefoni: {phone or '—'}")
            first_time = min((str(r.get('debt_time') or '') for r in all_rows), default='')
            self._c_created.setText(f'Jaratilg\'an waqti: {_fmt_dt_long(first_time)}')
            total = sum((float(r.get('amount', 0) or 0) for r in all_rows))
            self._c_total.setText(_fmt_money(total))
            self._c_debts_title.setText(f'Qarizlari ({len(all_rows)})')
            self._c_table.setRowCount(len(all_rows))
            for i, r in enumerate(all_rows):
                self._c_table.setItem(i, 0, QTableWidgetItem(str(r.get('id', i + 1))))
                amt = QTableWidgetItem(_fmt_money(float(r.get('amount', 0) or 0)))
                amt.setForeground(QColor(COL_RED))
                self._c_table.setItem(i, 1, amt)
                d, t = _split_dt(str(r.get('debt_time', '') or ''))
                self._c_table.setItem(i, 2, QTableWidgetItem(f'{d}\n{t}' if t else d))
                self._c_table.setRowHeight(i, 42)
            self.detail_stack.setCurrentIndex(2)
    def _mark_current_paid(self) -> None:
        if not self._current:
            return
        else:
            db.mark_debtor_paid(int(self._current['id']), True)
            self.reload()
            if self._on_changed:
                self._on_changed()
    def _pay_via_adjust(self) -> None:
        """Klient qarizini to\'lash — summa so\'raladi → Kassa: Qarzin to\'legenler."""
        if not self._current:
            return
        else:
            name = str(self._current.get('client_name') or '')
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
                amount = QDoubleSpinBox()
                amount.setRange(1, max(1.0, total))
                amount.setDecimals(0)
                amount.setSingleStep(1000)
                amount.setValue(total)
                amount.setSuffix(' so\'m')
                amount.setMinimumHeight(36)
                try:
                    from app.ui.widgets.money_spin import install_clear_zero_on_edit
                    install_clear_zero_on_edit(amount)
                except Exception:
                    pass
                form.addRow('To\'lanadigan summa:', amount)
                buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                buttons.button(QDialogButtonBox.StandardButton.Ok).setText('To\'lew')
                buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Biykar')
                buttons.accepted.connect(dlg.accept)
                buttons.rejected.connect(dlg.reject)
                form.addRow(buttons)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                else:
                    pay_amt = float(amount.value())
                    try:
                        paid = db.pay_client_debts(name, phone, amount=pay_amt)
                        QMessageBox.information(self, 'To\'landi', f'{_fmt_money(paid)} so\'m Qarzin to\'legenler ga yozildi.')
                    except Exception as e:
                        QMessageBox.critical(self, 'Xatolik', str(e))
                        return None
                    self.reload()
                    if self._on_changed:
                        self._on_changed()