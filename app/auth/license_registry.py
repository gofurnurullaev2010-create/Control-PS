"""Mijozlar ro\'yxati — faqat siz ko\'rasiz (server shart emas)."""
from __future__ import annotations
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
REGISTRY_NAME = 'mijozlar.json'
def _registry_path(base: Path | None=None) -> Path:
    if base is None:
        from app.core.runtime import app_dir
        base = app_dir()
    return base / REGISTRY_NAME
def _days_left(expiry: str | None) -> int | None:
    if not expiry:
        return
    else:
        try:
            return (date.fromisoformat(expiry) - date.today()).days
        except ValueError:
            return None
def _is_active(expiry: str | None, lic_type: str) -> bool:
    if lic_type == 'PERMANENT' or not expiry:
        return True
    else:
        days = _days_left(expiry)
        return days is not None and days >= 0
def save_client(hwid: str, lic_type: str, expiry: date | None, base_dir: Path | None=None, client_name: str='') -> None:
    """License berganingizda ro\'yxatga yozish."""
    path = _registry_path(base_dir)
    hwid = hwid.strip().upper()
    expiry_str = expiry.isoformat() if expiry else None
    entry = {'hwid': hwid, 'name': (client_name or hwid).strip(), 'type': lic_type, 'expiry': expiry_str, 'issued': datetime.now().strftime('%Y-%m-%d %H:%M')}
    data = {'clients': []}
    if path.is_file():
        try:
            with open(path, encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and isinstance(loaded.get('clients'), list):
                    data = loaded
        except (OSError, json.JSONDecodeError):
            pass
    clients = [c for c in data['clients'] if str(c.get('hwid', '')).upper() != hwid]
    clients.insert(0, entry)
    data['clients'] = clients
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
def load_clients(base_dir: Path | None=None) -> list[dict[str, Any]]:
    path = _registry_path(base_dir)
    if not path.is_file():
        return []
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return list(data.get('clients') or [])
        return []
    except (OSError, json.JSONDecodeError):
        return []
def format_roster(base_dir: Path | None=None) -> str:
    """Telefon/konsol uchun ro\'yxat matni."""
    clients = load_clients(base_dir)
    active = [c for c in clients if _is_active(c.get('expiry'), c.get('type', ''))]
    lines = ['============================================', '  MIJOZLAR RO\'YXATI', '============================================', f'  Jami bergan: {len(clients)} ta', f'  Faol: {len(active)} ta', '============================================', '']
    if not clients:
        lines.append('Hali hech kim yo\'q.')
        lines.append('License yaratganingizda avtomatik qo\'shiladi.')
        return '\n'.join(lines)
    else:
        for i, c in enumerate(clients, 1):
            hwid = c.get('hwid', '?')
            name = c.get('name') or hwid
            lic_type = c.get('type', '?')
            expiry = c.get('expiry')
            days = _days_left(expiry)
            if lic_type == 'PERMANENT' or not expiry:
                qoldiq = 'doimiy'
                holat = 'FAOL'
            else:
                if days is not None and days >= 0:
                    qoldiq = f'{days} kun'
                    holat = 'FAOL'
                else:
                    qoldiq = 'tugagan'
                    holat = 'TUGAGAN'
            lines.append(f'{i}. {name}')
            lines.append(f'   HWID: {hwid}')
            lines.append(f'   Qoldiq: {qoldiq}  [{holat}]')
            if expiry:
                lines.append(f'   Muddat: {expiry}')
            lines.append('')
        lines.append(f'Fayl: {_registry_path(base_dir)}')
        return '\n'.join(lines)