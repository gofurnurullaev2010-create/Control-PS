"""Control PS — online litsenziya tekshiruvi (server bilan)."""
from __future__ import annotations
import json
import logging
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from app.core.runtime import app_dir
logger = logging.getLogger(__name__)
_CACHE_FILE = 'license_online_cache.json'
@dataclass
class OnlineCheck:
    allowed: bool
    message: str = ''
    days_left: Optional[int] = None
    blocked: bool = False
def _config_path() -> Path:
    return app_dir() / 'license_online_config.json'
def load_online_config() -> dict:
    defaults = {'enabled': False, 'server_url': '', 'client_api_key': '', 'offline_grace_hours': 72}
    path = _config_path()
    if not path.is_file():
        return defaults
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {**defaults, **data}
        return defaults
    except (OSError, json.JSONDecodeError) as e:
        logger.warning('license_online_config: %s', e)
        return defaults
def is_online_enabled() -> bool:
    cfg = load_online_config()
    return bool(cfg.get('enabled')) and bool(str(cfg.get('server_url', '')).strip())
def _cache_path() -> Path:
    return app_dir() / _CACHE_FILE
def _read_cache() -> dict:
    p = _cache_path()
    if not p.is_file():
        return {}
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
def _write_cache(hwid: str, ok: bool, days_left: Optional[int]) -> None:
    try:
        _cache_path().write_text(json.dumps({'hwid': hwid, 'ok': ok, 'days_left': days_left, 'at': datetime.now().isoformat(timespec='seconds')}), encoding='utf-8')
    except OSError:
        return None
def _post(event: str, hwid: str, detail: str='', timeout: float=8.0) -> Optional[dict]:
    cfg = load_online_config()
    url = str(cfg.get('server_url', '')).rstrip('/') + '/api/v1/check'
    api_key = str(cfg.get('client_api_key', ''))
    body = json.dumps({'hwid': hwid.upper(), 'event': event, 'detail': detail}).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST', headers={'Content-Type': 'application/json', 'X-API-Key': api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode('utf-8'))
        except Exception:
            logger.error('Online license HTTP %s', e.code)
            return None
    except Exception as e:
        logger.warning('Online license ulanish: %s', e)
        return None
def report_tamper(hwid: str, detail: str) -> None:
    """Buzish urinishini serverga yuborish (bloklash uchun)."""
    if not is_online_enabled():
        return
    else:
        def _worker() -> None:
            result = _post('tamper', hwid, detail)
            if result:
                logger.warning('Tamper serverga yuborildi: %s', hwid)
        threading.Thread(target=_worker, daemon=True).start()
def report_tamper_sync(hwid: str, detail: str) -> OnlineCheck:
    """Buzish — darhol server javobi (blok xabari uchun)."""
    if not is_online_enabled():
        return OnlineCheck(allowed=False, message=detail, blocked=False)
    else:
        result = _post('tamper', hwid, detail, timeout=10.0)
        if result and result.get('blocked'):
            return OnlineCheck(allowed=False, blocked=True, message=result.get('message') or 'Buzish aniqlandi. Dastur bloklandi.')
        else:
            return OnlineCheck(allowed=False, message=detail, blocked=True)
def check_online(hwid: str) -> OnlineCheck:
    """Dastur ochilganda server tekshiruvi."""
    if not is_online_enabled():
        return OnlineCheck(allowed=True)
    result = _post('startup', hwid)
    if result is None:
        cfg = load_online_config()
        grace_h = int(cfg.get('offline_grace_hours', 72))
        cache = _read_cache()
        try:
            if cache.get('hwid') == hwid.upper() and cache.get('ok'):
                at = datetime.fromisoformat(cache['at'])
                if datetime.now() - at <= timedelta(hours=grace_h):
                    return OnlineCheck(allowed=True, message='Offline rejim (serverga ulanib bo\'lmadi)', days_left=cache.get('days_left'))
        except (ValueError, TypeError):
            pass
        return OnlineCheck(allowed=False, message='Litsenziya serveriga ulanib bo\'lmadi.\nInternet va server ishlayotganini tekshiring.')
    allowed = bool(result.get('allowed'))
    days_left = result.get('days_left')
    if allowed:
        _write_cache(hwid, True, days_left)
        return OnlineCheck(allowed=True, days_left=days_left)
    msg = str(result.get('message') or 'Server ruxsat bermadi')
    if result.get('blocked'):
        return OnlineCheck(allowed=False, blocked=True, message=msg, days_left=days_left)
    return OnlineCheck(allowed=False, message=msg, days_left=days_left)
def register_on_server(hwid: str, client_name: str, lic_type: str, expiry: str | None) -> bool:
    """Keygen: mijozni serverga ro\'yxatdan o\'tkazish."""
    cfg = load_online_config()
    admin_cfg = app_dir() / 'license_server_admin.json'
    token = ''
    server = str(cfg.get('server_url', '')).rstrip('/')
    if admin_cfg.is_file():
        try:
            with open(admin_cfg, encoding='utf-8') as f:
                ad = json.load(f)
            token = str(ad.get('admin_token', ''))
            if ad.get('server_url'):
                server = str(ad['server_url']).rstrip('/')
        except (OSError, json.JSONDecodeError):
            pass
    if not server or not token:
        return False
    else:
        body = json.dumps({'hwid': hwid.upper(), 'client_name': client_name or hwid, 'type': '2' if lic_type == 'PERMANENT' else '1', 'expiry': expiry}).encode('utf-8')
        req = urllib.request.Request(server + '/api/v1/register', data=body, method='POST', headers={'Content-Type': 'application/json', 'X-Admin-Token': token})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            return bool(data.get('ok'))
        except Exception as e:
            logger.warning('Server register: %s', e)
            return False