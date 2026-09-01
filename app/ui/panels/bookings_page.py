"""Bronlaw sahifasi — ro\'yxat + Bron mag\'liwmati; ✔ = mijoz keldi."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
def _fmt_money_time(value: str) -> str:
    text = (value or '').strip()
    if 'T' in text:
        d, t = text.split('T', 1)
        return f'{d} г. {t[:5]}'
    else:
        return text or '—'
def _time_key(value: str) -> str:
    text = (value or '').strip()
    if 'T' in text:
        return text.split('T', 1)[1][:5]
    else:
        return text[:5] if text else '—'
def _split_dt(value: str) -> tuple[str, str]:
    text = (value or '').strip()
    if 'T' in text:
        d, t = text.split('T', 1)
        return (d.replace('-', '.'), t[:8])
    else:
        return (text, '')
class BookingsPage(QWidget):
    """Bronlar jadvali + o\'ngda Bron mag\'liwmati. ✔ = keldi (ro\'yxatdan chiqadi)."""
    def __init__(self, parent=None, on_changed: Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._rows = []
        self._current = None
        self._search = ''
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Klient', 'Stol', 'Status', ''])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet('\n            QTableWidget { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; }\n            QHeaderView::section {\n                background: #F5F6F8; padding: 8px; border: none;\n                border-bottom: 1px solid #E5E7EB; font-weight: 800;\n            }\n            QTableWidget::item:selected { background: #EEF2FF; color: #202124; }\n            ')
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        root.addWidget(self.table, 1)
        self.detail = self._make_detail()
        root.addWidget(self.detail)
        self.reload()
    def _make_detail(self) -> QWidget:
        w = QFrame()
        w.setFixedWidth(340)
        w.setStyleSheet('QFrame { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel('Bron mag\'liwmati')
        title.setStyleSheet('color: #5F6368; font-size: 12px; font-weight: 700;')
        head.addWidget(title, 1)
        lay.addLayout(head)
        self._d_client = QLabel('Klientni tanlang')
        self._d_client.setWordWrap(True)
        self._d_client.setFont(QFont('Segoe UI', 16, QFont.Weight.Bold))
        lay.addWidget(self._d_client)
        self._d_stol = QLabel('Stol: —')
        self._d_stol.setStyleSheet('color: #16A34A; font-weight: 800; font-size: 14px;')
        lay.addWidget(self._d_stol)
        self._d_when = QLabel('Bronlaw waqti: —')
        self._d_when.setStyleSheet('color: #5F6368; font-size: 13px;')
        lay.addWidget(self._d_when)
        hist = QLabel('O\'zgerisler Tariyxi')
        hist.setStyleSheet('font-size: 13px; font-weight: 800; margin-top: 8px;')
        lay.addWidget(hist)
        self._hist = QVBoxLayout()
        self._hist.setSpacing(8)
        lay.addLayout(self._hist)
        lay.addStretch(1)
        arrived = QPushButton('✔  Mijoz keldi')
        arrived.setStyleSheet('QPushButton { background: #16A34A; color: white; font-weight: 900; border: none; border-radius: 8px; padding: 12px; }')
        arrived.clicked.connect(self._mark_arrived_current)
        lay.addWidget(arrived)
        edit_btn = QPushButton('✏  O\'zgartırıw')
        edit_btn.setStyleSheet('QPushButton { background: #EEF2FF; color: #1D4ED8; font-weight: 900; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px; }')
        edit_btn.clicked.connect(self._edit_current)
        lay.addWidget(edit_btn)
        del_btn = QPushButton('🗑  O\'chırıw')
        del_btn.setStyleSheet('QPushButton { background: #FEF2F2; color: #DC2626; font-weight: 900; border: 1px solid #FECACA; border-radius: 8px; padding: 12px; }')
        del_btn.clicked.connect(self._delete_current)
        lay.addWidget(del_btn)
        return w
    def set_search(self, text: str) -> None:
        self._search = (text or '').strip()
        self.reload()
    def reload(self) -> None:
        from app.ui.widgets.client_suggest import clean_client_fields
        rows = db.list_bookings(self._search, include_closed=False)
        rows = sorted(rows, key=lambda r: str(r.get('booking_time') or ''), reverse=True)
        self._rows = rows
        self.table.setRowCount(len(rows))
        self.table.verticalHeader().setDefaultSectionSize(52)
        for i, r in enumerate(rows):
            name, phone = clean_client_fields(str(r.get('client_name') or ''), str(r.get('phone') or ''))
            client = f'{name} - {phone}' if phone else name
            sid = str(r.get('station_id') or '')
            try:
                stol_name = db.get_station_display_name(sid)
            except Exception:
                stol_name = sid
            when = str(r.get('booking_time') or '')
            tshort = _time_key(when)
            stol_label = f'✔  {stol_name} ({tshort})'
            c_item = QTableWidgetItem(client)
            s_item = QTableWidgetItem(stol_label)
            s_item.setForeground(QColor('#16A34A'))
            s_item.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
            st_item = QTableWidgetItem('⏳  Ku\'tilmekte')
            st_item.setForeground(QColor('#D97706'))
            st_item.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
            self.table.setItem(i, 0, c_item)
            self.table.setItem(i, 1, s_item)
            self.table.setItem(i, 2, st_item)
            btn = QPushButton('✔')
            btn.setFixedSize(40, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip('Mijoz keldi — bronni yopish')
            btn.setStyleSheet('QPushButton { background: #DCFCE7; color: #16A34A; border: 1px solid #86EFAC; border-radius: 18px; font-weight: 900; font-size: 16px; }QPushButton:hover { background: #BBF7D0; }')
            bid = int(r.get('id') or 0)
            btn.clicked.connect(lambda _=False, booking_id=bid: self._mark_arrived(booking_id))
            self.table.setCellWidget(i, 3, btn)
            self.table.setRowHeight(i, 52)
        if not rows:
            self._current = None
            self._d_client.setText('Bron yo\'q')
            self._d_stol.setText('Stol: —')
            self._d_when.setText('Bronlaw waqti: —')
    def _on_row_selected(self) -> None:
        sel = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not sel:
            return
        else:
            idx = sel[0].row()
            if idx < 0 or idx >= len(self._rows):
                return None
            else:
                self._current = self._rows[idx]
                self._fill_detail(self._current)
    def _fill_detail(self, r: dict[str, Any]) -> None:
        from app.ui.widgets.client_suggest import clean_client_fields
        name, phone = clean_client_fields(str(r.get('client_name') or ''), str(r.get('phone') or ''))
        self._d_client.setText(f'{name} - {phone}' if phone else name)
        sid = str(r.get('station_id') or '')
        try:
            stol = db.get_station_display_name(sid)
        except Exception:
            stol = sid
        tshort = _time_key(str(r.get('booking_time') or ''))
        self._d_stol.setText(f'Stol: {stol} ({tshort})')
        self._d_when.setText(f"Bronlaw waqti: {_fmt_money_time(str(r.get('booking_time') or ''))}")
        while self._hist.count():
            item = self._hist.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        created = str(r.get('created_time') or r.get('booking_time') or '')
        for label, value, two_line in [('Jaratilg\'an waqti', created, True), ('Jaratqan adam', 'Kompyuter', False), ('Son\'g\'i o\'zgertilgen', created, True), ('Son\'g\'i o\'zgertken', 'Kompyuter', False)]:
            row = QHBoxLayout()
            cap = QLabel(label)
            cap.setStyleSheet('color: #5F6368; font-size: 12px;')
            row.addWidget(cap, 1)
            if two_line:
                d, t = _split_dt(value)
                box = QVBoxLayout()
                box.setSpacing(0)
                ld = QLabel(d or '—')
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
            self._hist.addWidget(host)
    def _mark_arrived_current(self) -> None:
        if not self._current:
            return
        else:
            self._mark_arrived(int(self._current.get('id') or 0))
    def _mark_arrived(self, booking_id: int) -> None:
        if not booking_id:
            return
        else:
            try:
                db.close_booking(booking_id)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
                return None
            self.reload()
            if self._on_changed:
                self._on_changed()
    def _station_ids_and_label(self):
        try:
            ids = list(db.list_station_ids())
        except Exception:
            ids = []
        def _label(sid: str) -> str:
            try:
                return db.get_station_display_name(sid)
            except Exception:
                return sid
        return (ids, _label)
    def _edit_current(self) -> None:
        if not self._current:
            QMessageBox.information(self, 'Bron', 'Avval bronni tanlang.')
            return
        else:
            from app.ui.dialogs.booking_dialog import BookingDialog
            ids, label_fn = self._station_ids_and_label()
            dlg = BookingDialog(self, station_ids=ids, station_label=label_fn, booking=self._current)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            else:
                try:
                    db.update_booking(int(self._current.get('id') or 0), client_name=dlg.client_name(), phone=dlg.client_phone(), station_id=dlg.station_id(), booking_time=dlg.booking_time_iso(), note=dlg.note.text())
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', str(e))
                    return None
                self.reload()
                if self._on_changed:
                    self._on_changed()
    def _delete_current(self) -> None:
        if not self._current:
            QMessageBox.information(self, 'Bron', 'Avval bronni tanlang.')
            return
        else:
            name = str(self._current.get('client_name') or '')
            confirm = QMessageBox.question(self, 'O\'chırıw', f'«{name}» bronı o\'chirilsinmi?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm != QMessageBox.StandardButton.Yes:
                return
            else:
                try:
                    db.delete_booking(int(self._current.get('id') or 0))
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', str(e))
                    return None
                self.reload()
                if self._on_changed:
                    self._on_changed()