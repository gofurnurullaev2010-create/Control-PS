"""QR ЗАКАЗ sozlamalari (app_settings)."""
from __future__ import annotations
import database as db
_KEY_ENABLED = 'zakaz_enabled'
_KEY_PORT = 'zakaz_port'
_KEY_PUBLIC = 'zakaz_public_base_url'
_DEFAULT_PORT = 8765
def get_zakaz_enabled() -> bool:
    return (db._setting_get(_KEY_ENABLED, '1') or '1').strip() in ['1', 'true', 'True', 'yes']
def set_zakaz_enabled(enabled: bool) -> None:
    db._setting_set(_KEY_ENABLED, '1' if enabled else '0')
def get_zakaz_port() -> int:
    try:
        p = int(db._setting_get(_KEY_PORT, str(_DEFAULT_PORT)) or _DEFAULT_PORT)
        return p if 1024 <= p <= 65535 else _DEFAULT_PORT
    except (TypeError, ValueError):
        return _DEFAULT_PORT
def set_zakaz_port(port: int) -> None:
    p = int(port)
    if not 1024 <= p <= 65535:
            p = _DEFAULT_PORT
    db._setting_set(_KEY_PORT, str(p))
def get_public_base_url() -> str:
    return (db._setting_get(_KEY_PUBLIC, '') or '').strip().rstrip('/')
def set_public_base_url(url: str) -> None:
    db._setting_set(_KEY_PUBLIC, (url or '').strip().rstrip('/'))
def get_google_webapp_url() -> str:
    return (db._setting_get('zakaz_google_webapp_url', '') or '').strip()
def set_google_webapp_url(url: str) -> None:
    db._setting_set('zakaz_google_webapp_url', (url or '').strip())
def zakaz_page_url(n: int, base: str | None=None, port: int | None=None) -> str:
    """QR uchun to\'liq URL."""
    from app.services.zakaz_server import zakaz_url
    b = (base if base is not None else get_public_base_url()).strip().rstrip('/')
    if b:
        return f'{b}/zakaz/{int(n)}'
    else:
        return zakaz_url(int(n), port if port is not None else get_zakaz_port())