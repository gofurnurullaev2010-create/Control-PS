"""\nControl PS - Parollar.\n\nIkki xil parol bor:\n  1) OPERATOR parollari (4 ta) — dasturga kirish uchun. Standart: 1111, 2222, 3333, 4444.\n     `operators.json` faylida salt bilan hash holatida saqlanadi.\n  2) ADMIN paroli (1 ta, alohida) — Admin panel uchun. `admin_password.hash` faylida.\n     Eski `password.hash` bo\'lsa, admin paroli sifatida ko\'chiriladi.\n"""
from __future__ import annotations
import hashlib
import json
import logging
import secrets
from pathlib import Path
from typing import Optional
from app.core.runtime import app_dir
logger = logging.getLogger(__name__)
OPERATOR_COUNT = 4
DEFAULT_OPERATOR_PASSWORDS = {1: '1111', 2: '2222', 3: '3333', 4: '4444'}
DEFAULT_ADMIN_PASSWORD = '0000'
_HASH_VERSION = 'v2'
_operators: dict[int, str] = {}
_admin_hash: str = ''
def _hash_with_salt(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120000).hex()
def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()
def hash_password(password: str, salt_hex: Optional[str]=None) -> str:
    """Yangi yozuv: v2$salt$hash"""
    if salt_hex is None:
        salt_hex = secrets.token_hex(16)
    digest = _hash_with_salt(password, salt_hex)
    return f'{_HASH_VERSION}${salt_hex}${digest}'
def _parse_stored(stored: str) -> tuple[str, str, str]:
    stored = (stored or '').strip()
    if stored.startswith(f'{_HASH_VERSION}$'):
        parts = stored.split('$', 2)
        if len(parts) == 3:
            return (parts[0], parts[1], parts[2])
    return ('', '', stored)
def _verify_against(stored: str, password: str) -> bool:
    ver, salt, digest = _parse_stored(stored)
    if ver == _HASH_VERSION and salt:
        return secrets.compare_digest(_hash_with_salt(password, salt), digest)
    else:
        return secrets.compare_digest(_legacy_sha256(password), (stored or '').strip())
def _operators_file() -> Path:
    return app_dir() / 'operators.json'
def _save_operators() -> None:
    data = {str(slot): h for slot, h in _operators.items()}
    _operators_file().write_text(json.dumps(data, indent=2), encoding='utf-8')
def load_operators() -> dict[int, str]:
    global _operators
    path = _operators_file()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            _operators = {int(k): str(v) for k, v in raw.items()}
        except Exception as e:
            logger.warning('operators.json o\'qishda xatolik: %s', e)
            _operators = {}
    changed = False
    if not _operators:
        _operators = {slot: hash_password(pw) for slot, pw in DEFAULT_OPERATOR_PASSWORDS.items()}
        changed = True
    else:
        for slot, pw in DEFAULT_OPERATOR_PASSWORDS.items():
            if slot not in _operators:
                _operators[slot] = hash_password(pw)
                changed = True
    if changed:
        _save_operators()
    return _operators
def operator_slots() -> list[int]:
    if not _operators:
        load_operators()
    return sorted(_operators.keys())
def identify_operator(input_password: str) -> Optional[int]:
    """Berilgan parol qaysi operatorga tegishli ekanini qaytaradi (1-4) yoki None."""
    if not _operators:
        load_operators()
    for slot in sorted(_operators):
        return slot if _verify_against(_operators[slot], input_password) else None
def verify_password(input_password: str) -> bool:
    """Dasturga kirish uchun: 4 operator parolidan biri to\'g\'ri bo\'lsa True."""
    return identify_operator(input_password) is not None
def change_operator_password(slot: int, new_password: str) -> bool:
    if slot not in DEFAULT_OPERATOR_PASSWORDS:
        return False
    else:
        if len(new_password) < 4:
            return False
        else:
            if not _operators:
                load_operators()
            _operators[slot] = hash_password(new_password)
            _save_operators()
            logger.info('%s-operator paroli yangilandi', slot)
            return True
def change_operator_password_by_old(old_password: str, new_password: str) -> Optional[int]:
    """Eski parol qaysi operatorga tegishli bo\'lsa, o\'shaning parolini almashtiradi.\n    Muvaffaqiyatda operator raqamini, aks holda None qaytaradi."""
    slot = identify_operator(old_password)
    if slot is None:
        return
    else:
        if change_operator_password(slot, new_password):
            return slot
        else:
            return None
def _admin_file() -> Path:
    return app_dir() / 'admin_password.hash'
def _legacy_password_file() -> Path:
    return app_dir() / 'password.hash'
def save_admin_password_hash(password: str) -> None:
    global _admin_hash
    _admin_hash = hash_password(password)
    _admin_file().write_text(_admin_hash + '\n', encoding='utf-8')
    logger.info('Admin paroli yangilandi')
def load_admin_password() -> str:
    global _admin_hash
    path = _admin_file()
    if path.is_file():
        _admin_hash = path.read_text(encoding='utf-8').strip()
        return _admin_hash
    else:
        legacy = _legacy_password_file()
        if legacy.is_file():
            _admin_hash = legacy.read_text(encoding='utf-8').strip()
            path.write_text(_admin_hash + '\n', encoding='utf-8')
            logger.info('Eski parol admin paroliga ko\'chirildi')
            return _admin_hash
        else:
            save_admin_password_hash(DEFAULT_ADMIN_PASSWORD)
            logger.warning('admin_password.hash topilmadi — vaqtincha standart admin parol (0000). Admin panel PAROL bo\'limidan o\'zgartiring.')
            return _admin_hash
def verify_admin_password(input_password: str) -> bool:
    if not _admin_hash:
        load_admin_password()
    if _verify_against(_admin_hash, input_password):
        ver, salt, _ = _parse_stored(_admin_hash)
        if ver == _HASH_VERSION and (not salt):
            save_admin_password_hash(input_password)
        return True
    else:
        return False
def change_admin_password(new_password: str) -> bool:
    if len(new_password) < 4:
        return False
    else:
        save_admin_password_hash(new_password)
        return True
def change_password(new_password: str) -> bool:
    """Eski kod admin parolini o\'zgartirsin (moslashuv)."""
    return change_admin_password(new_password)
load_operators()
load_admin_password()