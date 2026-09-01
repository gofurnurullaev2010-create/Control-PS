"""Bron kiritıw / tahrirlash oynasi — sana va soat alohida qatorlarda."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from PyQt6.QtCore import QDate, QTime, Qt
from PyQt6.QtWidgets import QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTimeEdit, QVBoxLayout
from app.ui.widgets.client_suggest import ClientSuggestEdit, clean_client_fields
class BookingDialog(QDialog):
    """Bron oynasi: yangi yoki tahrirlash."""
    def __init__(self, parent=None, *, station_ids: Optional[list[str]]=None, station_label: Optional[callable]=None, booking: Optional[dict[str, Any]]=None) -> None:
        super().__init__(parent)
        self._booking = booking
        self.setWindowTitle('Bronni o\'zgartırıw' if booking else 'Bron kiritıw')
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self.resize(560, 460)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.phone = QLineEdit()
        self.phone.setPlaceholderText('Telefon')
        self.phone.setMinimumHeight(36)
        self.name = ClientSuggestEdit(self, phone_edit=self.phone)
        self.name.setPlaceholderText('Ism yoki telefon oxirgi 4 raqam...')
        self.name.setMinimumHeight(36)
        self.station = QComboBox()
        self.station.setMinimumHeight(36)
        ids = list(station_ids or [])
        label_fn = station_label or (lambda s: s)
        for sid in ids:
            self.station.addItem(str(label_fn(sid)), sid)
        now = datetime.now()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat('dd.MM.yyyy')
        self.date_edit.setDate(QDate(now.year, now.month, now.day))
        self.date_edit.setMinimumHeight(36)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat('HH:mm')
        self.time_edit.setTime(QTime(now.hour, now.minute))
        self.time_edit.setMinimumHeight(36)
        self.note = QLineEdit()
        self.note.setPlaceholderText('Izoh (ixtiyoriy)')
        self.note.setMinimumHeight(36)
        form.addRow('Klient:', self.name)
        form.addRow('Stol:', self.station)
        form.addRow('Telefon:', self.phone)
        form.addRow('Sana:', self.date_edit)
        form.addRow('Soat:', self.time_edit)
        form.addRow('Izoh:', self.note)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Saqlaw')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Biykar etıw')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setStyleSheet('\n            QDialog { background: #FFFFFF; }\n            QLabel { color: #202124; font-weight: 700; font-size: 13px; }\n            QLineEdit, QComboBox, QDateEdit, QTimeEdit {\n                background: #F5F6F8; border: 1px solid #E5E7EB; border-radius: 8px;\n                padding: 8px 10px; color: #202124; font-size: 14px;\n            }\n            QPushButton {\n                min-height: 36px; padding: 8px 18px; border-radius: 8px; font-weight: 800;\n            }\n            ')
        if booking:
            self._load_booking(booking)
    def _load_booking(self, booking: dict[str, Any]) -> None:
        name, phone = clean_client_fields(str(booking.get('client_name') or ''), str(booking.get('phone') or ''))
        self.name.setText(name)
        self.phone.setText(phone)
        sid = str(booking.get('station_id') or '')
        idx = self.station.findData(sid)
        if idx < 0:
            for i in range(self.station.count()):
                if str(self.station.itemText(i)).strip().lower() == sid.strip().lower():
                    idx = i
                    break
                else:
                    if str(self.station.itemData(i) or '') == sid:
                        idx = i
                        break
        if idx >= 0:
            self.station.setCurrentIndex(idx)
        when = str(booking.get('booking_time') or '')
        try:
            if 'T' in when:
                dt = datetime.fromisoformat(when)
            else:
                dt = datetime.fromisoformat(when.replace(' ', 'T'))
            self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            self.time_edit.setTime(QTime(dt.hour, dt.minute))
        except Exception:
            pass
        self.note.setText(str(booking.get('note') or ''))
    def booking_time_iso(self) -> str:
        d = self.date_edit.date()
        t = self.time_edit.time()
        return f'{d.year():04d}-{d.month():02d}-{d.day():02d}T{t.hour():02d}:{t.minute():02d}:00'
    def station_id(self) -> str:
        return str(self.station.currentData() or '')
    def client_name(self) -> str:
        name, _ = clean_client_fields(self.name.text(), self.phone.text())
        return name
    def client_phone(self) -> str:
        _, phone = clean_client_fields(self.name.text(), self.phone.text())
        return phone