"""Klient qidiruv: ism yoki telefon oxirgi 4 raqam — avto-to\'ldirish."""
from __future__ import annotations
from typing import List, Optional, Tuple
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtWidgets import QCompleter, QLineEdit, QWidget
import database as db
def _looks_like_phone(text: str) -> bool:
    digits = ''.join((ch for ch in text or '' if ch.isdigit()))
    return len(digits) >= 7
def clean_client_fields(name: str, phone: str='') -> Tuple[str, str]:
    """Ism va telefonni ajratib tozalash (takrorlangan raqamlarni olib tashlash)."""
    name = (name or '').strip()
    phone = (phone or '').strip()
    parts = [p.strip() for p in name.replace(' - ', ' — ').split(' — ') if p.strip()]
    name_parts = []
    phones = []
    for p in parts:
        if _looks_like_phone(p):
            phones.append(''.join((ch for ch in p if ch.isdigit() or ch in '+')))
        else:
            name_parts.append(p)
    if not name_parts and parts and (not _looks_like_phone(parts[0])):
                name_parts = [parts[0]]
    clean_name = name_parts[0] if name_parts else ''
    if not phone and phones:
        phone = phones[0]
    else:
        if phone:
            phone = ''.join((ch for ch in phone if ch.isdigit() or ch in '+'))
    if not clean_name and _looks_like_phone(name):
            phone = phone or ''.join((ch for ch in name if ch.isdigit() or ch in '+'))
            clean_name = ''
    return (clean_name, phone)
def load_clients() -> List[dict]:
    """Klientler ro\'yxati (qarzdorlar + bronlar), tozalangan."""
    seen = {}
    def _add(name: str, phone: str) -> None:
        name, phone = clean_client_fields(name, phone)
        if not name and (not phone):
                return
        key = (name.lower(), phone)
        if key not in seen:
            seen[key] = {'name': name, 'phone': phone}
    try:
        for r in db.list_debtors('', include_paid=True):
            _add(str(r.get('client_name') or ''), str(r.get('phone') or ''))
    except Exception:
        pass
    try:
        for r in db.list_bookings('', include_closed=True):
            _add(str(r.get('client_name') or ''), str(r.get('phone') or ''))
    except Exception:
        pass
    return list(seen.values())
class ClientSuggestEdit(QLineEdit):
    """Yozganda Klientlardan taklif; tanlansa faqat ism (+ telefon maydoni)."""
    client_picked = pyqtSignal(str, str)
    def __init__(self, parent: Optional[QWidget]=None, phone_edit: Optional[QLineEdit]=None, *, as_phone_field: bool=False) -> None:
        super().__init__(parent)
        self._phone_edit = phone_edit
        self._as_phone = as_phone_field
        self._clients = load_clients()
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(self._completer)
        self._applying = False
        self._rebuild_model('')
        self.textEdited.connect(self._on_text)
        self._completer.activated[str].connect(self._on_activated)
    def set_phone_edit(self, phone_edit: QLineEdit) -> None:
        self._phone_edit = phone_edit
    def reload_clients(self) -> None:
        self._clients = load_clients()
        self._rebuild_model(self.text())
    def _display(self, c: dict) -> str:
        name = c.get('name') or ''
        phone = c.get('phone') or ''
        if name and phone:
            return f'{name} — {phone}'
        else:
            return name or phone
    def _matches(self, query: str) -> List[dict]:
        q = (query or '').strip().lower()
        q_name, _ = clean_client_fields(q, '')
        q = (q_name or q).lower()
        digits = ''.join((ch for ch in query or '' if ch.isdigit()))
        out = []
        for c in self._clients:
            name = (c.get('name') or '').lower()
            phone = c.get('phone') or ''
            phone_digits = ''.join((ch for ch in phone if ch.isdigit()))
            ok = False
            if q and q in name:
                    ok = True
            if digits and len(digits) >= 2 and (digits in phone_digits):
                        ok = True
            if digits and len(digits) == 4 and phone_digits.endswith(digits):
                        ok = True
            if ok:
                out.append(c)
        return out[:40]
    def _rebuild_model(self, query: str) -> None:
        labels = [self._display(c) for c in self._matches(query)]
        if not (query or '').strip():
            labels = [self._display(c) for c in self._clients[:40]]
        self._model.setStringList(labels)
    def _on_text(self, text: str) -> None:
        if self._applying:
            return
        else:
            self._rebuild_model(text)
    def _apply_pick(self, name: str, phone: str) -> None:
        name, phone = clean_client_fields(name, phone)
        self._applying = True
        try:
            if self._as_phone:
                self.setText(phone)
            else:
                self.setText(name)
                if self._phone_edit is not None:
                    self._phone_edit.setText(phone)
            self.client_picked.emit(name, phone)
        finally:
            self._applying = False
    def _on_activated(self, label: str) -> None:
        label = (label or '').strip()
        name, phone = ('', '')
        for c in self._clients:
            if self._display(c) == label:
                name, phone = (c.get('name') or '', c.get('phone') or '')
                break
        if not name and (not phone):
                if ' — ' in label or ' - ' in label:
                    name, phone = clean_client_fields(label.replace(' - ', ' — '), '')
                else:
                    if _looks_like_phone(label):
                        phone = label
                    else:
                        name = label
        self._apply_pick(name, phone)
    def focusOutEvent(self, event) -> None:
        if not self._as_phone and (not self._applying):
                raw = self.text()
                if ' — ' in raw or ' - ' in raw:
                    name, phone = clean_client_fields(raw, self._phone_edit.text() if self._phone_edit else '')
                    if name != raw:
                        self._apply_pick(name, phone)
        super().focusOutEvent(event)