"""\n\nControl PS - HWID litsenziyasi (HMAC imzoli).\n\nlicense.key:\n\n  HWID=XXXX-XXXX-XXXX-XXXX\n\n  KEY=32_HEX\n\n  TYPE=MONTHLY|PERMANENT\n\n  EXPIRY=YYYY-MM-DD   (faqat MONTHLY)\n\n  SIGN=64_HEX         — HWID+EXPIRY imzosi (o\'zgartirib bo\'lmaydi)\n\n"""
from __future__ import annotations
import hashlib
import hmac
import logging
import secrets
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple
from app.core.network_time import get_network_time, trusted_today
from app.core.runtime import app_dir
logger = logging.getLogger(__name__)
_SALT = 'CONTROL_PS_SECRET_SALT_2026_BY_ADMIN!@#'
_SIGN_SECRET = 'CONTROL_PS_HMAC_SIGN_2026!@#'
MONTHLY_EXPIRY_DAY = 10
_TIME_GUARD_FILE = '.cps_timeguard'
def _time_guard_path() -> Path:
    return app_dir() / _TIME_GUARD_FILE
def _time_guard_sign(hwid: str, day: date) -> str:
    payload = f'TIMEGUARD|{hwid.strip().upper()}|{day.isoformat()}'
    return hmac.new(_SIGN_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:24].upper()
def _read_time_guard(hwid: str) -> tuple[Optional[date], str]:
    """Oxirgi ishga tushgan sana.\n\n    Qaytaradi: (sana|None, holat)\n      holat: \"ok\" | \"missing\" | \"hwid_mismatch\" | \"corrupt\"\n    """
    path = _time_guard_path()
    if not path.is_file():
        return (None, 'missing')
    try:
        raw = path.read_text(encoding='utf-8').strip()
        parts = raw.split('|')
        if len(parts) != 2:
            return (None, 'corrupt')
        last = date.fromisoformat(parts[0])
        if not secrets.compare_digest(_time_guard_sign(hwid, last), parts[1]):
            return (last, 'hwid_mismatch')
        return (last, 'ok')
    except (OSError, ValueError):
        return (None, 'corrupt')
def _write_time_guard(hwid: str, day: date) -> None:
    path = _time_guard_path()
    sign = _time_guard_sign(hwid, day)
    path.write_text(f'{day.isoformat()}|{sign}\n', encoding='utf-8')
def _reset_time_guard(hwid: str, day: date, reason: str) -> None:
    path = _time_guard_path()
    logger.warning('Vaqt himoyasi qayta yoziladi (%s): %s', reason, path)
    try:
        if path.is_file():
            path.unlink()
    except OSError as e:
        logger.warning('Eski timeguard o\'chirilmadi: %s', e)
    _write_time_guard(hwid, day)
def _check_system_clock(hwid: str) -> Optional[LicenseCheck]:
    """Sana orqaga surilsa — blok. HWID o\'zgarsa timeguard yangilanadi (PC ko\'chirish)."""
    nt = get_network_time()
    today = trusted_today()
    last, status = _read_time_guard(hwid)
    if status in ['hwid_mismatch', 'corrupt']:
        _reset_time_guard(hwid, today, status)
        last = None
    if last is not None and today < last:
        logger.warning('Tizim sanasi orqaga surilgan: %s < %s', today, last)
        return LicenseCheck(False, hwid, f'Tizim sanasi orqaga surilgan ({today.isoformat()} < {last.isoformat()}). To\'g\'ri sanani o\'rnating yoki internet ulang.')
    else:
        nt.sync()
        _write_time_guard(hwid, max(today, last or today))
def get_next_monthly_expiry(from_day: date | None=None) -> date:
    """Keyingi oyning 10-sanasini qaytaradi (oylik litsenziya tugash kuni)."""
    d = from_day or date.today()
    month = d.month + 1
    year = d.year
    if month > 12:
        month = 1
        year += 1
    return date(year, month, MONTHLY_EXPIRY_DAY)
def format_expiry_iso(expiry: date) -> str:
    return expiry.isoformat()
@dataclass
class LicenseCheck:
    valid: bool
    hwid: str
    message: str = ''
@dataclass
class LicenseStatus:
    """Admin MUDDAT bo\'limi va eslatma uchun litsenziya holati."""
    valid: bool
    hwid: str
    lic_type: str
    expiry: Optional[date]
    days_left: Optional[int]
    monthly_renew_day: int
    current_date: date
    current_time: str
    time_source: str
    show_expiry_warning: bool
    status_text: str
    message: str = ''
@dataclass
class ParsedLicense:
    hwid: str
    key: str
    lic_type: str
    expiry: Optional[date]
    sign: str
def get_hwid() -> str:
    try:
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NO_WINDOW
        cmd = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], capture_output=True, text=True, creationflags=creationflags, timeout=5)
        output = cmd.stdout.strip().split('\n')
        hwid = ''
        for line in output:
            if 'UUID' not in line and line.strip():
                    hwid = line.strip()
                    break
        if not hwid or hwid == 'FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF':
            cmd = subprocess.run(['wmic', 'diskdrive', 'get', 'serialnumber'], capture_output=True, text=True, creationflags=creationflags, timeout=5)
            output = cmd.stdout.strip().split('\n')
            for line in output:
                if 'SerialNumber' not in line and line.strip():
                        hwid = line.strip()
                        break
        if not hwid:
            hwid = 'UNKNOWN-HWID-FALLBACK'
        m = hashlib.sha256()
        m.update(hwid.encode('utf-8'))
        full_hash = m.hexdigest().upper()
        return f'{full_hash[:4]}-{full_hash[4:8]}-{full_hash[8:12]}-{full_hash[12:16]}'
    except Exception as e:
        logger.error('HWID olishda xatolik: %s', e)
        return 'ERROR-HWID-MAKE'
def get_license_key_expected(hwid: str) -> str:
    m = hashlib.sha256()
    m.update((hwid.upper() + _SALT).encode('utf-8'))
    return m.hexdigest()[:32].upper()
def _sign_payload(hwid: str, expiry: Optional[date]) -> str:
    exp = expiry.isoformat() if expiry else 'PERMANENT'
    return f'{hwid.strip().upper()}|{exp}'
def compute_license_sign(hwid: str, expiry: Optional[date]) -> str:
    """HWID va muddat uchun HMAC-SHA256 imzo."""
    payload = _sign_payload(hwid, expiry)
    return hmac.new(_SIGN_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest().upper()
def build_license_content(hwid: str, expiry: Optional[date]) -> str:
    """Imzoli license.key matni."""
    hwid = hwid.strip().upper()
    key = get_license_key_expected(hwid)
    lic_type = 'MONTHLY' if expiry else 'PERMANENT'
    sign = compute_license_sign(hwid, expiry)
    lines = [f'HWID={hwid}', f'KEY={key}', f'TYPE={lic_type}']
    if expiry:
        lines.append(f'EXPIRY={format_expiry_iso(expiry)}')
    lines.append(f'SIGN={sign}')
    return '\n'.join(lines) + '\n'
def write_license_file(hwid: str, expiry: Optional[date], path: Path) -> Path:
    path.write_text(build_license_content(hwid, expiry), encoding='utf-8')
    return path
def _license_path() -> Path:
    return app_dir() / 'license.key'
def _parse_license_file(text: str) -> ParsedLicense:
    hwid = ''
    key = ''
    lic_type = ''
    expiry = None
    sign = ''
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        else:
            upper = line.upper()
            if upper.startswith('HWID='):
                hwid = line.split('=', 1)[1].strip().upper()
            else:
                if upper.startswith('KEY='):
                    key = line.split('=', 1)[1].strip().upper()
                else:
                    if upper.startswith('TYPE='):
                        lic_type = line.split('=', 1)[1].strip().upper()
                    else:
                        if upper.startswith('EXPIRY='):
                            val = line.split('=', 1)[1].strip()
                            try:
                                expiry = datetime.strptime(val, '%Y-%m-%d').date()
                            except ValueError:
                                logger.warning('EXPIRY formati noto\'g\'ri: %s', val)
                        else:
                            if upper.startswith('SIGN='):
                                sign = line.split('=', 1)[1].strip().upper()
                            else:
                                if not key and len(line) >= 16 and ('=' not in line):
                                            key = line.upper()
    return ParsedLicense(hwid=hwid, key=key, lic_type=lic_type, expiry=expiry, sign=sign)
def verify_license() -> Tuple[bool, str]:
    """Eski API: (valid, hwid)."""
    r = verify_license_full()
    return (r.valid, r.hwid)
def verify_license_full() -> LicenseCheck:
    hwid = get_hwid()
    clock_err = _check_system_clock(hwid)
    if clock_err is not None:
        return clock_err
    else:
        expected_key = get_license_key_expected(hwid)
        path = _license_path()
        if not path.is_file():
            return LicenseCheck(False, hwid, 'Litsenziya fayli (license.key) topilmadi. Dasturchiga HWID yuboring.')
        else:
            try:
                text = path.read_text(encoding='utf-8')
                lic = _parse_license_file(text)
                if not lic.sign:
                    return LicenseCheck(False, hwid, 'Litsenziya fayli eski yoki imzolanmagan.\nDasturchidan yangi imzoli license.key oling.')
                else:
                    if not lic.key:
                        return LicenseCheck(False, hwid, 'license.key ichida KEY topilmadi.')
                    else:
                        if not secrets.compare_digest(lic.key, expected_key):
                            return LicenseCheck(False, hwid, 'Litsenziya kaliti noto\'g\'ri (HWID mos emas).')
                        else:
                            if lic.hwid and (not secrets.compare_digest(lic.hwid, hwid)):
                                return LicenseCheck(False, hwid, 'Litsenziya boshqa kompyuter uchun (HWID mos emas).')
                            else:
                                expected_sign = compute_license_sign(hwid, lic.expiry)
                                if not secrets.compare_digest(lic.sign, expected_sign):
                                    return LicenseCheck(False, hwid, 'Litsenziya fayli o\'zgartirilgan yoki buzilgan!\nEXPIRY yoki boshqa qatorni o\'zgartirmang.\nDasturchidan yangi license.key oling.')
                                else:
                                    today = trusted_today()
                                    if lic.expiry is not None and today >= lic.expiry:
                                        return LicenseCheck(False, hwid, f"Litsenziya muddati tugagan ({lic.expiry.strftime('%d.%m.%Y')}).\nHar oyning {MONTHLY_EXPIRY_DAY}-sanada yangilanadi.\nDasturchiga HWID yuboring: {hwid}")
                                    else:
                                        if lic.expiry is not None:
                                            days_left = (lic.expiry - today).days
                                            logger.info('Litsenziya amal qiladi: %s (%s kun qoldi)', lic.expiry, days_left)
                                        return LicenseCheck(True, hwid, '')
            except OSError as e:
                logger.error('license.key o\'qilmadi: %s', e)
                return LicenseCheck(False, hwid, 'Litsenziya faylini o\'qib bo\'lmadi.')
def get_license_status() -> LicenseStatus:
    """Admin panel MUDDAT bo\'limi uchun to\'liq litsenziya ma\'lumoti."""
    hwid = get_hwid()
    nt = get_network_time()
    today = trusted_today()
    now = nt.now()
    if nt.is_online():
        time_source = 'Internet (O\'zbekiston)'
    else:
        if nt.is_synced():
            time_source = 'Kesh (oxirgi internet vaqti)'
        else:
            time_source = 'Mahalliy kompyuter'
    current_time = now.strftime('%d.%m.%Y %H:%M:%S')
    base = dict(hwid=hwid, monthly_renew_day=MONTHLY_EXPIRY_DAY, current_date=today, current_time=current_time, time_source=time_source)
    path = _license_path()
    if not path.is_file():
        return LicenseStatus(valid=False, lic_type='NONE', expiry=None, days_left=None, show_expiry_warning=False, status_text='Litsenziya topilmadi', message='license.key fayli yo\'q.', **base)
    else:
        try:
            lic = _parse_license_file(path.read_text(encoding='utf-8'))
            expected_key = get_license_key_expected(hwid)
            if not lic.key or not secrets.compare_digest(lic.key, expected_key):
                return LicenseStatus(valid=False, lic_type=lic.lic_type or 'UNKNOWN', expiry=lic.expiry, days_left=None, show_expiry_warning=False, status_text='Noto\'g\'ri litsenziya', message='Litsenziya kaliti HWID bilan mos emas.', **base)
            else:
                if lic.lic_type == 'PERMANENT' or lic.expiry is None:
                    return LicenseStatus(valid=True, lic_type='PERMANENT', expiry=None, days_left=None, show_expiry_warning=False, status_text='Doimiy litsenziya', message='Muddat cheklovi yo\'q.', **base)
                else:
                    days_left = (lic.expiry - today).days
                    show_warning = days_left <= 1
                    if days_left <= 0:
                        status_text = 'Muddati tugagan'
                        message = f"Litsenziya {lic.expiry.strftime('%d.%m.%Y')} sanada tugadi."
                        valid = False
                    else:
                        if days_left == 1:
                            status_text = 'Ertaga tugaydi!'
                            message = f"Ertaga ({lic.expiry.strftime('%d.%m.%Y')}) litsenziya tugaydi."
                            valid = True
                        else:
                            status_text = 'Amal qilmoqda'
                            message = f'Har oyning {MONTHLY_EXPIRY_DAY}-sanada yangilanadi.'
                            valid = True
                    return LicenseStatus(valid=valid, lic_type='MONTHLY', expiry=lic.expiry, days_left=max(days_left, 0), show_expiry_warning=show_warning and days_left > 0, status_text=status_text, message=message, **base)
        except OSError as e:
            logger.error('license.key o\'qilmadi: %s', e)
            return LicenseStatus(valid=False, lic_type='UNKNOWN', expiry=None, days_left=None, show_expiry_warning=False, status_text='Xatolik', message='Litsenziya faylini o\'qib bo\'lmadi.', **base)