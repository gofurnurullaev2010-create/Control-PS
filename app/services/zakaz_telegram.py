"""QR ЗАКАЗ — Telegram orqali (istalgan Wi‑Fi / internet)."""
from __future__ import annotations
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Optional
from app.services.telegram_notify import get_telegram_config
logger = logging.getLogger(__name__)
ZakazCallback = Callable[[int], None]
_poller: Optional['ZakazTelegramPoller'] = None
def _http_json(token: str, method: str, payload: Optional[dict]=None, timeout: int=35) -> dict:
    url = f'https://api.telegram.org/bot{token}/{method}'
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method='POST' if data else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))
def fetch_bot_username(token: str) -> str:
    """@username (atsiz)."""
    try:
        r = _http_json(token, 'getMe', timeout=15)
        if r.get('ok'):
            return str((r.get('result') or {}).get('username') or '').strip()
        return ''
    except Exception as e:
        logger.warning('getMe: %s', e)
        return ''
def telegram_zakaz_url(username: str, n: int) -> str:
    u = (username or '').strip().lstrip('@')
    return f'https://t.me/{u}?start=z{int(n)}'
def parse_zakaz_payload(text: str) -> Optional[int]:
    """z1 / zakaz1 / zakaz_1 / start z1 → 1..5."""
    raw = (text or '').strip()
    if raw.startswith('/start'):
        parts = raw.split(maxsplit=1)
        raw = parts[1].strip() if len(parts) > 1 else ''
    raw = raw.strip().lstrip('/')
    m = re.match('^(?:z|zakaz[_-]?)(\\d)$', raw, re.I)
    if not m:
        return
    n = int(m.group(1))
    return n if 1 <= n <= 5 else None
class ZakazTelegramPoller:
    """getUpdates — /start zN → ЗАКАЗ tugmasi; bosilganda callback."""
    def __init__(self, on_zakaz: ZakazCallback) -> None:
        self.on_zakaz = on_zakaz
        self._stop = threading.Event()
        self._thread = None
        self._offset = 0
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    def start(self) -> None:
        if self.running:
            return
        else:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name='zakaz-tg')
            self._thread.start()
    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            t.join(timeout=2.0)

    def _loop(self) -> None:
        logger.info('Zakaz Telegram poller boshlandi')
        cleared_hook = False
        while not self._stop.is_set():
            try:
                token, _ = get_telegram_config()
                if not token:
                    time.sleep(2.0)
                    continue
                if not cleared_hook:
                    try:
                        _http_json(token, 'deleteWebhook', {'drop_pending_updates': False}, timeout=10)
                    except Exception:
                        pass
                    cleared_hook = True
                data = _http_json(token, 'getUpdates', {'offset': self._offset, 'timeout': 25, 'allowed_updates': ['message', 'callback_query']}, timeout=35)
                if not data.get('ok'):
                    time.sleep(2.0)
                    continue
                for upd in data.get('result') or []:
                    self._offset = max(self._offset, int(upd.get('update_id', 0)) + 1)
                    try:
                        self._handle(token, upd)
                    except Exception:
                        logger.exception('Zakaz update')
            except urllib.error.HTTPError as e:
                logger.warning('Telegram getUpdates HTTP %s', e.code)
                time.sleep(3.0)
            except Exception as e:
                logger.warning('Telegram poll: %s', e)
                time.sleep(2.0)
        logger.info("Zakaz Telegram poller to'xtadi")
    def _handle(self, token: str, upd: dict) -> None:
        cq = upd.get('callback_query')
        if cq:
            data = str(cq.get('data') or '')
            n = None
            m = re.match('^zakaz[:_](\\d)$', data, re.I)
            if m:
                n = int(m.group(1))
            if n and 1 <= n <= 5:
                        try:
                            _http_json(token, 'answerCallbackQuery', {'callback_query_id': cq.get('id'), 'text': f'ЗАКАЗ #{n}'}, timeout=10)
                        except Exception:
                            pass
                        chat = (cq.get('message') or {}).get('chat') or {}
                        try:
                            _http_json(token, 'sendMessage', {'chat_id': chat.get('id'), 'text': f'✓ ЗАКАЗ #{n} qabul qilindi'}, timeout=10)
                        except Exception:
                            pass
                        if self.on_zakaz:
                            self.on_zakaz(n)
            return None
        else:
            msg = upd.get('message') or {}
            text = str(msg.get('text') or '')
            n = parse_zakaz_payload(text)
            if n is None:
                return
            else:
                chat_id = (msg.get('chat') or {}).get('id')
                if not chat_id:
                    return
                else:
                    kb = {'inline_keyboard': [[{'text': 'ЗАКАЗ', 'callback_data': f'zakaz:{n}'}]]}
                    _http_json(token, 'sendMessage', {'chat_id': chat_id, 'text': f'Eagle Playstation · №{n}\n\nЗАКАЗ tugmasini bosing:', 'reply_markup': kb}, timeout=15)
def start_zakaz_telegram(on_zakaz: ZakazCallback) -> ZakazTelegramPoller:
    global _poller
    stop_zakaz_telegram()
    _poller = ZakazTelegramPoller(on_zakaz)
    _poller.start()
    return _poller
def stop_zakaz_telegram() -> None:
    global _poller
    if _poller is not None:
        _poller.stop()
        _poller = None
def get_zakaz_poller() -> Optional[ZakazTelegramPoller]:
    return _poller