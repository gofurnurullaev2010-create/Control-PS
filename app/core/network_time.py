"""Internet orqali O\'zbekiston vaqti — internet yo\'q bo\'lsa oxirgi vaqtdan davom etadi."""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from app.core.runtime import app_dir
logger = logging.getLogger(__name__)
UZ_TZ = timezone(timedelta(hours=5))
_SYNC_FILE = '.cps_ntsync'
_SYNC_SECRET = 'CONTROL_PS_NETWORK_TIME_2026!@#'
_ONLINE_FRESH_SEC = 300
def _sync_path() -> Path:
    return app_dir() / _SYNC_FILE
def _sync_sign(iso_dt: str, mono: float) -> str:
    payload = f'NTSYNC|{iso_dt}|{mono:.6f}'
    return hmac.new(_SYNC_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:24].upper()
def internet_available() -> bool:
    """Qisqa timeout — UI oqimida chaqirilmasin."""
    for host in ['8.8.8.8', '1.1.1.1']:
        try:
            with socket.create_connection((host, 53), timeout=0.4):
                return True
        except OSError:
            continue
    return False
def _parse_uz_datetime(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UZ_TZ)
    else:
        return dt.astimezone(UZ_TZ)
def _local_uz_now() -> datetime:
    """UTC orqali taxminiy O\'zbekiston vaqti (faqat kesh yo\'q bo\'lganda)."""
    return datetime.now(timezone.utc).astimezone(UZ_TZ)
def _fetch_from_worldtimeapi() -> Optional[datetime]:
    urls = ('https://worldtimeapi.org/api/timezone/Asia/Tashkent', 'http://worldtimeapi.org/api/timezone/Asia/Tashkent')
    headers = {'User-Agent': 'ControlPS/1.0'}
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            dt_raw = data.get('datetime') or data.get('utc_datetime')
            if dt_raw:
                return _parse_uz_datetime(dt_raw)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug('worldtimeapi (%s): %s', url, e)
    return None
def _fetch_from_http_date() -> Optional[datetime]:
    urls = ('http://google.com', 'http://www.microsoft.com')
    headers = {'User-Agent': 'ControlPS/1.0'}
    for url in urls:
        try:
            req = urllib.request.Request(url, method='HEAD', headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                hdr = resp.headers.get('Date')
            if not hdr:
                continue
            else:
                dt = parsedate_to_datetime(hdr)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(UZ_TZ)
        except (OSError, urllib.error.URLError, ValueError, TypeError) as e:
            logger.debug('HTTP Date (%s): %s', url, e)
def fetch_uz_datetime() -> Optional[datetime]:
    if not internet_available():
        return
    else:
        dt = _fetch_from_worldtimeapi()
        if dt is None:
            dt = _fetch_from_http_date()
        if dt is not None:
            logger.info('Tarmoq vaqti olindi: %s', dt.strftime('%d.%m.%Y %H:%M:%S'))
        return dt
class NetworkTimeService:
    """Internet bo\'lsa sinxron; yo\'q bo\'lsa oxirgi vaqtdan monotonic bilan davom etadi."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._anchor_real = None
        self._anchor_mono = None
        self._last_network_at = None
        self._last_sync_attempt = 0.0
        self._load_cached_sync()
    def _set_anchor(self, moment: datetime) -> None:
        self._anchor_real = moment
        self._anchor_mono = time.monotonic()
    def _load_cached_sync(self) -> None:
        path = _sync_path()
        if not path.is_file():
            return
        raw = path.read_text(encoding='utf-8').strip()
        parts = raw.split('|')
        if len(parts) != 3:
            return
        try:
            iso_dt, mono_s, sign = parts
            if not secrets.compare_digest(_sync_sign(iso_dt, float(mono_s)), sign):
                logger.warning('Tarmoq vaqti keshi buzilgan')
                return
            synced_at = _parse_uz_datetime(iso_dt)
            now_uz = _local_uz_now()
            gap = max(timedelta(0), now_uz - synced_at)
            resumed = synced_at + gap
            with self._lock:
                self._set_anchor(resumed)
                self._last_network_at = synced_at
            logger.info('Vaqt keshi yuklandi: oxirgi sinxron %s, davom %s', synced_at.strftime('%d.%m.%Y %H:%M:%S'), resumed.strftime('%d.%m.%Y %H:%M:%S'))
        except (OSError, ValueError):
            return None
    def _save_cached_sync(self, real: datetime, mono: float) -> None:
        sign = _sync_sign(real.isoformat(), mono)
        try:
            _sync_path().write_text(f'{real.isoformat()}|{mono:.6f}|{sign}\n', encoding='utf-8')
        except OSError as e:
            logger.warning('Tarmoq vaqti keshi yozilmadi: %s', e)
    def sync(self, *, force: bool=False) -> bool:
        """Internet bo\'lsa yangilaydi; yo\'q bo\'lsa mavjud vaqtdan davom etadi."""
        with self._lock:
            has_anchor = self._anchor_real is not None
        now_mono = time.monotonic()
        if not force and has_anchor and (self._last_network_at is not None) and (now_mono - self._last_sync_attempt < 30):
                        return True
        self._last_sync_attempt = now_mono
        if not internet_available():
            return has_anchor
        else:
            dt = fetch_uz_datetime()
            if dt is None:
                return has_anchor
            else:
                with self._lock:
                    self._set_anchor(dt)
                    self._last_network_at = dt
                    mono = self._anchor_mono or time.monotonic()
                self._save_cached_sync(dt, mono)
                return True
    def _network_age_sec(self) -> float:
        with self._lock:
            if self._last_network_at is None:
                return float('inf')
            else:
                last = self._last_network_at
        return (_local_uz_now() - last).total_seconds()
    def is_online(self) -> bool:
        """UI uchun: so‘nggi muvaffaqiyatli sinxron yoshiga qarab (socket yo‘q)."""
        return self.is_synced() and self._network_age_sec() <= _ONLINE_FRESH_SEC
    def is_synced(self) -> bool:
        with self._lock:
            return self._anchor_real is not None
    def now(self) -> datetime:
        with self._lock:
            real = self._anchor_real
            mono = self._anchor_mono
        if real is not None and mono is not None:
            elapsed = time.monotonic() - mono
            if elapsed >= 0:
                return real + timedelta(seconds=elapsed)
        return _local_uz_now()
    def today(self) -> date:
        return self.now().date()
    def system_date_mismatch(self) -> Optional[int]:
        with self._lock:
            pass
        if self._anchor_real is None:
            return None
        system = date.today()
        return (system - self.today()).days
    def format_display(self) -> tuple[str, str]:
        """UI soati — har soniya internet probe qilmaydi (qotish oldini oladi)."""
        now = self.now()
        text = now.strftime('%d.%m.%Y  %H:%M:%S')
        with self._lock:
            synced = self._anchor_real is not None
        age = self._network_age_sec()
        if synced and age <= _ONLINE_FRESH_SEC:
            return (f'🇺🇿 {text}', '#00E676')
        else:
            if synced:
                return (f'🇺🇿 {text}  (offline)', '#FFD54F')
            else:
                return (f'🇺🇿 {text}  (mahalliy)', '#FFAB40')
_service: Optional[NetworkTimeService] = None
def get_network_time() -> NetworkTimeService:
    global _service
    if _service is None:
        _service = NetworkTimeService()
    return _service
def trusted_now() -> datetime:
    return get_network_time().now()
def trusted_now_naive() -> datetime:
    """Seans/DB uchun: onlayn (yoki offline kesh) vaqt, tzinfosiz.\n\n    Internet bo\'lsa O\'zbekiston vaqti; uzilsa oxirgi sinxrondan monotonic bilan davom etadi.\n    """
    dt = trusted_now()
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    else:
        return dt
def trusted_today() -> date:
    return get_network_time().today()