"""QR ЗАКАЗ — Google Apps Script web app (istalgan Wi‑Fi)."""
from __future__ import annotations
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional
from app.services.zakaz_settings import get_google_webapp_url
logger = logging.getLogger(__name__)
ZakazCallback = Callable[[int], None]
_poller: Optional['ZakazGooglePoller'] = None
def google_zakaz_url(base: str, n: int) -> str:
    b = (base or '').strip().rstrip('/')
    if not b:
        return ''
    else:
        sep = '&' if '?' in b else '?'
        return f'{b}{sep}n={int(n)}'
def _fetch_json(url: str, timeout: int=25) -> object:
    req = urllib.request.Request(url, headers={'User-Agent': 'ControlPS-Zakaz/1.0'}, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8', errors='replace').strip()
    if not raw:
        return []
    else:
        return json.loads(raw)
class ZakazGooglePoller:
    def __init__(self, on_zakaz: ZakazCallback) -> None:
        self.on_zakaz = on_zakaz
        self._stop = threading.Event()
        self._thread = None
        self._seen = set()
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    def start(self) -> None:
        if self.running:
            return
        else:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name='zakaz-google')
            self._thread.start()
    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            t.join(timeout=2.0)

    def _loop(self) -> None:
        logger.info('Zakaz Google poller boshlandi')
        while not self._stop.is_set():
            try:
                base = get_google_webapp_url()
                if not base:
                    time.sleep(2.0)
                    continue
                poll_url = google_zakaz_url(base, 1).replace('n=1', 'action=poll')
                if '?' in base:
                    poll_url = f"{base.rstrip('/')}&action=poll"
                else:
                    poll_url = f"{base.rstrip('/')}?action=poll"
                data = _fetch_json(poll_url, timeout=20)
                items = data if isinstance(data, list) else []
                for item in items:
                    try:
                        if isinstance(item, dict):
                            n = int(item.get('n') or 0)
                            key = f"{n}:{item.get('t')}"
                        else:
                            n = int(item)
                            key = f'{n}:{time.time()}'
                        if n < 1 or n > 5:
                            continue
                        if key in self._seen:
                            continue
                        self._seen.add(key)
                        if len(self._seen) > 200:
                            self._seen = set(list(self._seen)[-100:])
                        if self.on_zakaz:
                            self.on_zakaz(n)
                    except Exception:
                        logger.exception('Google zakaz item')
                time.sleep(1.2)
            except urllib.error.HTTPError as e:
                logger.warning('Google poll HTTP %s', e.code)
                time.sleep(3.0)
            except Exception as e:
                logger.warning('Google poll: %s', e)
                time.sleep(2.0)
        logger.info("Zakaz Google poller to'xtadi")
def start_zakaz_google(on_zakaz: ZakazCallback) -> ZakazGooglePoller:
    global _poller
    stop_zakaz_google()
    _poller = ZakazGooglePoller(on_zakaz)
    _poller.start()
    return _poller
def stop_zakaz_google() -> None:
    global _poller
    if _poller is not None:
        _poller.stop()
        _poller = None