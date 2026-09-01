"""Cloudflare quick tunnel — istalgan internetdan lokal ЗАКАЗ serverga."""
from __future__ import annotations
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from app.core.paths import application_dir
logger = logging.getLogger(__name__)
_URL_RE = re.compile('https://[a-z0-9-]+\\.trycloudflare\\.com', re.I)
_proc: Optional[subprocess.Popen] = None
_public_url: str = ''
_lock = threading.Lock()
def cloudflared_path() -> Optional[Path]:
    candidates = [application_dir() / 'tools' / 'cloudflared.exe', application_dir() / 'cloudflared.exe', Path(__file__).resolve().parents[2] / 'tools' / 'cloudflared.exe']
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.extend([Path(meipass) / 'tools' / 'cloudflared.exe', Path(meipass) / 'cloudflared.exe'])
    for p in candidates:
        if p.is_file():
            return p
def get_public_url() -> str:
    with _lock:
        return _public_url
def stop_tunnel() -> None:
    global _proc
    global _public_url
    with _lock:
        _public_url = ''
        proc = _proc
        _proc = None
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            return None
def start_tunnel(local_port: int, wait_sec: float=25.0) -> str:
    """Lokal portni internetga ochadi. URL qaytaradi yoki \'\'."""
    global _proc
    stop_tunnel()
    exe = cloudflared_path()
    if exe is None:
        logger.warning('cloudflared.exe topilmadi')
        return ''
    else:
        creation = 0
        if sys.platform == 'win32':
            creation = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        try:
            proc = subprocess.Popen([str(exe), 'tunnel', '--url', f'http://127.0.0.1:{int(local_port)}', '--no-autoupdate'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=creation)
        except Exception as e:
            logger.warning('cloudflared start: %s', e)
            return ''
        with _lock:
            _proc = proc
        found = ''
        registered = threading.Event()
        deadline = time.time() + max(8.0, wait_sec)
        def _reader() -> None:
            global _public_url
            nonlocal found
            assert proc.stdout is not None
            for line in proc.stdout:
                line = (line or '').strip()
                if not line:
                    continue
                else:
                    logger.info('cloudflared: %s', line)
                    m = _URL_RE.search(line)
                    if m and (not found):
                            found = m.group(0).rstrip('/')
                            with _lock:
                                _public_url = found
                    if 'Registered tunnel connection' in line:
                        registered.set()
        t = threading.Thread(target=_reader, daemon=True, name='cloudflared-out')
        t.start()
        while time.time() < deadline and (not found):
                if proc.poll() is not None:
                    break
                time.sleep(0.15)
        remain = max(0.0, deadline - time.time())
        registered.wait(timeout=min(20.0, remain + 5.0))
        if found:
            time.sleep(1.5)
        return found