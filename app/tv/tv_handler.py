"""TV avtomatlashtirish: Android TV (ADB), LG webOS, Samsung Tizen, Wake-on-LAN.\n\nPlatformalar:\n  - Android TV (Artel, Immer, TCL, …) — ADB + controlps-lock.apk overlay\n  - LG webOS — controlps-lock.ipk + HTTP gate (port 8099)\n  - Samsung Tizen — controlps-lock.wgt + HTTP gate yoki samsungtvws\n\nKutubxonalar o\'rnatilmagan bo\'lsa, funksiyalar xavfsiz ravishda log qiladi va o\'tkazib yuboradi.\n"""
from __future__ import annotations
import logging
import re
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional
import socket
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import json
import os
import tempfile
import time
if sys.platform == 'win32':
    import subprocess
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    CREATE_NO_WINDOW = 0
from . import tv_platforms
from . import vidaa_platform
logger = logging.getLogger(__name__)
_adb_device_locks: dict[str, threading.Lock] = {}
_adb_device_locks_guard = threading.Lock()
_adb_connect_cache: dict[str, float] = {}
def _lock_for_device(device: str) -> threading.Lock:
    with _adb_device_locks_guard:
        if device not in _adb_device_locks:
            _adb_device_locks[device] = threading.Lock()
        return _adb_device_locks[device]
ANDROID_ADB_BRANDS = frozenset({'xiaomi', 'ziffler', 'avalon', 'immer', 'premier', 'shivaki', 'sony', 'artel', 'changhong', 'yasin', 'roison', 'rulls', 'tcl'})
CONTROLPS_LOCK_PACKAGE = 'uz.controlps.lock'
CONTROLPS_LOCK_ACTIVITY = f'{CONTROLPS_LOCK_PACKAGE}/.LockActivity'
CONTROLPS_LOCK_APK_NAME = 'controlps-lock.apk'
LOCK_OVERLAY_SHOW_ACTION = 'uz.controlps.lock.SHOW_OVERLAY'
LOCK_OVERLAY_HIDE_ACTION = 'uz.controlps.lock.HIDE_OVERLAY'
HDMI_PRESERVE_BLOCK = os.environ.get('CONTROLPS_LEGACY_FULLSCREEN_LOCK', '').strip().lower() not in ['1', 'true', 'yes', 'on']
_saved_screen_brightness: dict[str, str] = {}
_RESUME_STATE_REMOTE = '/sdcard/controlps_resume_state.json'
_resume_state_memory: dict[str, dict] = {}
_LOCK_SCREEN_BG_REMOTE = '/sdcard/lock_screen_bg.png'
_LOCK_SCREEN_BG_LOCAL_NAMES = ('lock_screen_bg.png', 'lock_screen_bg.jpg', 'lock_screen_bg.jpeg', 'lock_bg.png', 'lock_bg.jpg')
_LOCK_GATE_HTTP_PATH = '/controlps/tv-should-lock'
_LOCK_GATE_URL_REMOTE = '/sdcard/controlps_lock_gate.url'
_main_app_lock_gate = False
_gate_lock = threading.Lock()
_active_tv_hosts: set[str] = set()
_active_tv_lock = threading.Lock()
_webos_watchdog_stop_events: dict[str, threading.Event] = {}
_webos_watchdog_guard = threading.Lock()
WEBOS_LOCK_WATCHDOG_INTERVAL = 2.0
_webos_online_state: dict[str, bool] = {}
_webos_last_poweroff: dict[str, float] = {}
WEBOS_POWEROFF_COOLDOWN_S = 60.0
_webos_connectivity_started = False
WEBOS_CONNECTIVITY_INTERVAL = 20.0
def normalize_tv_host(raw: str) -> str:
    """TV IP yoki host:port dan faqat host qaytaradi."""
    raw = (raw or '').strip()
    if not raw:
        return ''
    else:
        if raw.count(':') == 1 and (not raw.startswith('[')):
            return raw.split(':', 1)[0].strip()
        else:
            return raw
def stop_webos_lock_watchdog(tv_ip: str) -> None:
    """webOS lock watchdog ni to\'xtatish (START / seans faol)."""
    host = normalize_tv_host(tv_ip)
    if not host:
        return
    else:
        with _webos_watchdog_guard:
            stop_event = _webos_watchdog_stop_events.pop(host, None)
        if stop_event:
            stop_event.set()
            print(f'[TVHandler] webOS lock watchdog to\'xtatildi: {host}')
def stop_all_webos_lock_watchdogs() -> None:
    with _webos_watchdog_guard:
        hosts = list(_webos_watchdog_stop_events.keys())
    for host in hosts:
        stop_webos_lock_watchdog(host)
def start_webos_lock_watchdog(tv_ip: str, params: Optional[dict]=None) -> None:
    """Bo\'sh stol: Home/Exit dan keyin blok ekranni qayta ochish."""
    host = normalize_tv_host(tv_ip)
    if not host or not params:
        return None
    else:
        stop_webos_lock_watchdog(host)
        stop_event = threading.Event()
        with _webos_watchdog_guard:
            _webos_watchdog_stop_events[host] = stop_event
        def _runner() -> None:
            while not stop_event.wait(WEBOS_LOCK_WATCHDOG_INTERVAL):
                while True:
                    if not _main_app_lock_gate_active():
                        continue
                    else:
                        if not _should_lock_tv(host):
                            continue
                        else:
                            tv_platforms.webos_ensure_lock(host, params)
        threading.Thread(target=_runner, daemon=True, name=f'ControlPS-webOS-lock-{host}').start()
        print(f'[TVHandler] webOS lock watchdog yoqildi: {host}')
def start_webos_connectivity_monitor() -> None:
    """TV o\'chib-yonishi / WiFi qayta ulanganda avtomatik ulanish va bloklash."""
    global _webos_connectivity_started
    if _webos_connectivity_started:
        return
    else:
        _webos_connectivity_started = True
        def _runner() -> None:
            while True:
                try:
                    _poll_webos_tv_connectivity()
                except Exception as e:
                    logger.warning('webOS connectivity: %s', e)
                time.sleep(WEBOS_CONNECTIVITY_INTERVAL)
        threading.Thread(target=_runner, daemon=True, name='ControlPS-webOS-connectivity').start()
        print('[TVHandler] webOS avtomatik ulanish monitori yoqildi')
def _poll_webos_tv_connectivity() -> None:
    """Har bir LG TV: tarmoq qaytsa config yuborish va bo\'sh stolni bloklash."""
    import database as db
    if not _main_app_lock_gate_active():
        return
    else:
        live = tv_platforms.sync_webos_device_mappings_from_ares()
        pc_ip = _get_local_ip()
        for sid in db.list_station_ids():
            row = db.get_tv_settings(sid)
            if not tv_platforms.is_webos_brand(row.brand):
                continue
            else:
                host = normalize_tv_host(row.tv_ip or '')
                if not host:
                    continue
                else:
                    online = tv_platforms.webos_port_open(host)
                    was_online = _webos_online_state.get(host, False)
                    _webos_online_state[host] = online
                    if not online:
                        continue
                    else:
                        gate_url = _gate_url_for_host(host)
                        hdmi = int(row.hdmi_input or 1)
                        params = tv_platforms.build_launch_params(pc_ip, host, gate_url, hdmi_input=hdmi)
                        if not was_online:
                            tv_platforms.clear_ares_device_cache(host)
                            if host in live:
                                tv_platforms.register_webos_device_mapping(host, live[host])
                            print(f'[TVHandler] webOS TV qayta onlayn: {host} ({sid})')
                            tv_platforms.webos_push_station_config(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=hdmi)
                        if db.active_session_for_station(sid):
                            continue
                        else:
                            if not _should_lock_tv(host):
                                continue
                            else:
                                if tv_platforms.WEBOS_POWER_OFF_ON_STOP:
                                    now = time.time()
                                    last = float(_webos_last_poweroff.get(host, 0.0) or 0.0)
                                    if not was_online or now - last >= WEBOS_POWEROFF_COOLDOWN_S:
                                        stop_webos_lock_watchdog(host)
                                        tv_platforms.webos_power_off(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=hdmi)
                                        _webos_last_poweroff[host] = now
                                else:
                                    lock_params = tv_platforms.build_launch_params(pc_ip, host, gate_url, action='lock', hdmi_input=hdmi)
                                    tv_platforms.webos_ensure_lock(host, lock_params)
                                    start_webos_lock_watchdog(host, lock_params)
def sync_webos_initial_lock_from_db() -> None:
    """Dastur ochilganda bo\'sh webOS stollar uchun bir marta blok (qayta launch yo\'q)."""
    import database as db
    pc_ip = _get_local_ip()
    for sid in db.list_station_ids():
        if db.active_session_for_station(sid):
            continue
        else:
            row = db.get_tv_settings(sid)
            if not tv_platforms.is_webos_brand(row.brand):
                continue
            else:
                if tv_platforms.WEBOS_POWER_OFF_ON_STOP:
                    continue
                else:
                    host = normalize_tv_host(row.tv_ip or '')
                    if not host:
                        continue
                    else:
                        if not _main_app_lock_gate_active() or not _should_lock_tv(host):
                            continue
                        else:
                            gate_url = _gate_url_for_host(host)
                            params = tv_platforms.build_launch_params(pc_ip, host, gate_url, action='lock', hdmi_input=int(row.hdmi_input or 1))
                            tv_platforms.webos_launch(host, params)
def register_tv_session(tv_ip: str) -> None:
    """START / faol seans: TV gate HTTP bu TV uchun bloklashni to\'xtatadi."""
    host = normalize_tv_host(tv_ip)
    if not host:
        return
    else:
        tv_platforms.cancel_webos_lock_tasks(host)
        with _active_tv_lock:
            _active_tv_hosts.add(host)
        print(f'[TVHandler] TV seans faol (gate ochiq): {host}')
def unregister_tv_session(tv_ip: str) -> None:
    """STOP: TV yana gate orqali bloklanishi mumkin."""
    host = normalize_tv_host(tv_ip)
    if not host:
        return
    else:
        with _active_tv_lock:
            _active_tv_hosts.discard(host)
        print(f'[TVHandler] TV seans tugadi (gate yopildi): {host}')
def sync_active_tv_sessions_from_db() -> None:
    """Dastur qayta ochilganda bazadagi band stollar TV ro\'yxatini tiklash."""
    import database as db
    with _active_tv_lock:
        _active_tv_hosts.clear()
    for sid in db.list_station_ids():
        if not db.active_session_for_station(sid):
            continue
        else:
            row = db.get_tv_settings(sid)
            host = normalize_tv_host(row.tv_ip or '')
            if host:
                register_tv_session(host)
def _gate_url_for_host(host: str) -> str:
    base = f'http://{_get_local_ip()}:8099{_LOCK_GATE_HTTP_PATH}'
    host = normalize_tv_host(host)
    if host:
        return f'{base}?tv={host}'
    else:
        return base
def _should_lock_tv(tv_host: str) -> bool:
    """True = TV bloklashi kerak (HTTP 200)."""
    if not _main_app_lock_gate_active():
        return False
    else:
        tv_host = normalize_tv_host(tv_host)
        with _active_tv_lock:
            if not tv_host:
                return True
            else:
                return tv_host not in _active_tv_hosts
ALLOW_LEGACY_HTML_LOCK = os.environ.get('CONTROLPS_LEGACY_HTML_LOCK', '').strip().lower() in ['1', 'true', 'yes', 'on']
def _android_lock_ui_already_foreground(adb_path: str, device: str) -> bool:
    """Lock oynasi yoki overlay blok faol bo\'lsa True."""
    if _overlay_lock_visible(adb_path, device):
        return True
    else:
        try:
            w = subprocess.run([adb_path, '-s', device, 'shell', 'dumpsys', 'window'], capture_output=True, text=True, timeout=4, creationflags=CREATE_NO_WINDOW)
            win_out = (w.stdout or '') + (w.stderr or '')
            for line in win_out.splitlines():
                if 'mCurrentFocus' not in line and 'mFocusedApp' not in line:
                        continue
                if CONTROLPS_LOCK_PACKAGE in line:
                    return True
                else:
                    low = line.lower()
                    if 'htmlviewer' in low and ('lock.html' in low or '/sdcard/lock' in low):
                        return True
                    else:
                        if ':8099/' in line and 'lock.html' in low:
                            return True
        except Exception:
            pass
        try:
            a = subprocess.run([adb_path, '-s', device, 'shell', 'dumpsys', 'activity', 'activities'], capture_output=True, text=True, timeout=4, creationflags=CREATE_NO_WINDOW)
            act_out = (a.stdout or '') + (a.stderr or '')
            for line in act_out.splitlines():
                ls = line.strip()
                if 'mResumedActivity' not in ls and 'ResumedActivity' not in ls and ('topResumedActivity' not in ls):
                            continue
                if CONTROLPS_LOCK_PACKAGE in ls:
                    return True
                else:
                    low = ls.lower()
                    if 'htmlvieweractivity' in low:
                        return True
        except Exception:
            pass
        return False
def _resource_dir() -> Path:
    """PyInstaller va development holatida resurs papkasini qaytaradi."""
    from app.core.runtime import app_dir
    return app_dir()
_local_ipCache = None
def _auto_detect_local_ip() -> str:
    """Tashqi ulanish uchun ishlatiladigan LAN IP (eng to\'g\'ri taxmin)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        if ip and ip != '0.0.0.0':
            return ip
    except Exception:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
    return '127.0.0.1'
def _all_local_ipv4() -> set[str]:
    """Shu kompyuterning barcha IPv4 manzillari."""
    addrs = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip:
                addrs.add(ip)
    except Exception:
        pass
    auto = _auto_detect_local_ip()
    if auto and auto != '127.0.0.1':
            addrs.add(auto)
    return addrs
def _get_local_ip():
    global _local_ipCache
    if _local_ipCache:
        return _local_ipCache
    else:
        auto = _auto_detect_local_ip()
        fixed = ''
        try:
            from app.core.runtime import load_json_config
            fixed = (load_json_config('tv_config.json', {}).get('pc_ip') or '').strip()
        except Exception:
            fixed = ''
        if fixed:
            if fixed == auto or fixed in _all_local_ipv4():
                _local_ipCache = fixed
                return _local_ipCache
            else:
                print(f'[TVHandler] WARNING: tv_config.json pc_ip={fixed} bu kompyuterga mos emas — avto-aniqlangan {auto} ishlatiladi (pc_ip ni yangilang yoki bo\'sh qoldiring)')
        _local_ipCache = auto
        return _local_ipCache
def _parse_tv_host_port(tv_ip: str) -> tuple[str, int]:
    """TVHandler bilan bir xil: host va ADB port."""
    raw = (tv_ip or '').strip()
    if not raw:
        return ('', 5555)
    host, sep, port_text = raw.rpartition(':')
    if sep and host and port_text.isdigit():
        port = int(port_text)
        if 1 <= port <= 65535:
                return (host.strip(), port)
    return (raw, 5555)
def set_main_app_lock_gate(opened: bool) -> None:
    """Control PS asosiy oynasi ochiq/yopiqligi — TV boot HTTP tekshiruvi."""
    global _main_app_lock_gate
    with _gate_lock:
        _main_app_lock_gate = bool(opened)
    if not opened:
        stop_all_webos_lock_watchdogs()
def _main_app_lock_gate_active() -> bool:
    with _gate_lock:
        return _main_app_lock_gate
def start_lock_gate_http_server() -> None:
    """Asosiy dastur kirganda chaqiring: port 8099 + /controlps/tv-should-lock."""
    _ensure_http_server()
_server_started = False
def _ensure_http_server():
    global _server_started
    if _server_started:
        return
    else:
        _server_started = True
        serve_dir = str(_resource_dir())
        _allowed_static = frozenset({'/lock.html'})
        class ControlPSHttpHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=serve_dir, **kwargs)
            def log_message(self, format, *args):
                return
            def list_directory(self, path):
                self.send_error(403, 'Forbidden')
            def do_GET(self) -> None:
                try:
                    parsed = urlparse(self.path)
                    path = parsed.path
                    if path == _LOCK_GATE_HTTP_PATH:
                        params = parse_qs(parsed.query or '')
                        tv_host = (params.get('tv') or [''])[0]
                        ok = _should_lock_tv(tv_host)
                        body = b'1\n' if ok else b'0\n'
                        self.send_response(200 if ok else 503)
                        self.send_header('Content-Type', 'text/plain; charset=utf-8')
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    if path in _allowed_static:
                        return super().do_GET()
                    self.send_error(403, 'Forbidden')
                except Exception:
                    logger.exception('HTTP handler xatolik')
                    self.send_error(403, 'Forbidden')
        try:
            server = HTTPServer(('0.0.0.0', 8099), ControlPSHttpHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            print(f'[TVHandler] HTTP Server started on port 8099 (IP: {_get_local_ip()})')
        except Exception as e:
            print(f'[TVHandler] Failed to start HTTP server: {e}')
def _adb_tcp_try_connect(adb_path: str, host: str, port: int) -> bool:
    """Bir martalik ADB tarmoq ulanishi (broadcast uchun)."""
    if not host:
        return False
    else:
        device = f'{host}:{port}'
        for _ in range(3):
            res = subprocess.run([adb_path, 'connect', device], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            out = (res.stdout or '').lower()
            if 'connected' in out or 'already connected' in out:
                return True
            else:
                time.sleep(1)
        return False
def _push_lock_gate_url_to_tv(adb_path: str, device: str) -> None:
    """TV ga PC manzili (HTTP gate) — bootda faqat dastur ochiq bo\'lsa bloklash."""
    tmp_path = None
    try:
        _ensure_http_server()
        host = device.split(':', 1)[0] if device else ''
        gate_url = f'{_gate_url_for_host(host)}\n'
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', delete=False, suffix='.txt') as tf:
            tf.write(gate_url)
            tmp_path = tf.name
        r = subprocess.run([adb_path, '-s', device, 'push', tmp_path, _LOCK_GATE_URL_REMOTE], capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0:
            print(f'[TVHandler] Pushed lock gate URL -> TV {_LOCK_GATE_URL_REMOTE}')
        else:
            err = (r.stderr or r.stdout or '' or '').strip()
            if err:
                print(f'[TVHandler] WARNING: gate URL push failed: {err[:200]}')
    except Exception as e:
        print(f'[TVHandler] WARNING: gate URL push: {e}')
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                return
def broadcast_lock_gate_url_to_all_android_tvs_background() -> None:
    """Asosiy oyna ochilganda fon fonda barcha Android TVlarga gate faylini yuborish."""
    def _runner() -> None:
        try:
            broadcast_lock_gate_url_to_all_android_tvs()
            broadcast_smart_tv_config_background(sync=True)
        except Exception as e:
            logger.warning('TV gate URL broadcast: %s', e)
            print(f'[TVHandler] TV gate URL broadcast: {e}')
    threading.Thread(target=_runner, daemon=True, name='ControlPS-GateBroadcast').start()
def broadcast_smart_tv_config_background(*, sync: bool=False) -> None:
    """webOS va Tizen TV larga gate URL ni launch params orqali yuborish."""
    def _runner() -> None:
        try:
            broadcast_smart_tv_config()
        except Exception as e:
            logger.warning('Smart TV config broadcast: %s', e)
            print(f'[TVHandler] Smart TV config broadcast: {e}')
    if sync:
        _runner()
    else:
        threading.Thread(target=_runner, daemon=True, name='ControlPS-SmartTVBroadcast').start()
def broadcast_smart_tv_config() -> None:
    import database as db
    _ensure_http_server()
    pc_ip = _get_local_ip()
    stations = []
    for sid in db.list_station_ids():
        row = db.get_tv_settings(sid)
        brand = (row.brand or '').lower()
        if not tv_platforms.is_smart_tv_brand(brand):
            continue
        else:
            raw = (row.tv_ip or '').strip()
            if not raw:
                continue
            else:
                host = normalize_tv_host(raw)
                if host:
                    stations.append((host, brand, pc_ip, int(row.hdmi_input or 1)))
    if stations:
        tv_platforms.broadcast_smart_tv_config(stations, _gate_url_for_host)
        print(f'[TVHandler] Smart TV gate config yuborildi: {len(stations)} ta')
def broadcast_lock_gate_url_to_all_android_tvs() -> None:
    import database as db
    _ensure_http_server()
    adb_path = _get_adb_path()
    seen = set()
    for sid in db.list_station_ids():
        row = db.get_tv_settings(sid)
        if (row.brand or '').lower() not in ANDROID_ADB_BRANDS:
            continue
        raw = (row.tv_ip or '').strip()
        if not raw:
            continue
        host, port = _parse_tv_host_port(raw)
        if not host:
            continue
        key = f'{host}:{port}'
        if key in seen:
            continue
        seen.add(key)
        if not _adb_tcp_try_connect(adb_path, host, port):
            continue
        device = f'{host}:{port}'
        gate_url = f'{_gate_url_for_host(host)}\n'
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', delete=False, suffix='.txt') as tf:
                tf.write(gate_url)
                tmp_path = tf.name
            r = subprocess.run([adb_path, '-s', device, 'push', tmp_path, _LOCK_GATE_URL_REMOTE], capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)
            if r.returncode == 0:
                print(f'[TVHandler] Pushed gate URL config -> {device} ({gate_url.strip()})')
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
def _get_adb_path() -> str:
    """ADB fayl yo\'lini topish."""
    adb_in_path = shutil.which('adb')
    if adb_in_path:
        return adb_in_path
    else:
        common_paths = [Path('C:/platform-tools/adb.exe'), Path('C:/Program Files/platform-tools/adb.exe'), Path('C:/Android/platform-tools/adb.exe')]
        for p in common_paths:
            if p.exists():
                return str(p)
        return 'adb'
def _get_lock_apk_path() -> Path:
    """TV ga yuklanadigan APK: ildizdagi controlps-lock.apk yoki eng yangi app-debug.apk."""
    base = _resource_dir()
    candidates = [base / CONTROLPS_LOCK_APK_NAME, base / 'controlps-lock-android' / 'app' / 'build' / 'outputs' / 'apk' / 'debug' / 'app-debug.apk']
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return candidates[0]
    else:
        return max(existing, key=lambda p: p.stat().st_mtime)
def _push_lock_screen_assets_to_tv(adb_path: str, device: str, *, push_html: bool=False) -> None:
    """Fon rasmini /sdcard ga yuboradi (native Lock APK uchun). lock.html faqat ALLOW_LEGACY_HTML_LOCK=1 bo\'lsa."""
    root = _resource_dir()
    remote_html = '/sdcard/lock.html'
    remote_bg = _LOCK_SCREEN_BG_REMOTE
    pushed = False
    for name in _LOCK_SCREEN_BG_LOCAL_NAMES:
        src = root / name
        if not src.is_file():
            continue
        else:
            r = subprocess.run([adb_path, '-s', device, 'push', str(src), remote_bg], capture_output=True, timeout=120, creationflags=CREATE_NO_WINDOW)
            if r.returncode == 0:
                print(f'[TVHandler] Pushed lock background ({name}) -> TV {remote_bg}')
                pushed = True
                break
            else:
                err = (r.stderr or r.stdout or b'').decode('utf-8', errors='ignore') if isinstance(r.stderr, bytes) else r.stderr or r.stdout or ''
                print(f'[TVHandler] WARNING: lock background push failed ({name}): {err[:200]}')
    any_local = any(((root / n).is_file() for n in _LOCK_SCREEN_BG_LOCAL_NAMES))
    if not pushed:
        if any_local:
            print('[TVHandler] WARNING: fon rasmi dastur papkasida bor, lekin TV ga surilmadi (ADB / joy).')
        else:
            print('[TVHandler] INFO: fon rasmi yo\'q — ControlPS Lock qora fon ishlatadi. Rasm uchun dastur yonidagi lock_screen_bg.png yoki .jpg qo\'ying.')
    _push_lock_gate_url_to_tv(adb_path, device)
    if not push_html:
        return
    else:
        lock = root / 'lock.html'
        if not lock.exists():
            return
        else:
            html = lock.read_text(encoding='utf-8')
            html_tv = html.replace('url(\'lock_screen_bg.png\')', 'url(\'file:///sdcard/lock_screen_bg.png\')', 1)
            tmp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.html', delete=False) as tf:
            tf.write(html_tv)
            tmp_path = tf.name
        r2 = subprocess.run([adb_path, '-s', device, 'push', tmp_path, remote_html], capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW)
        if r2.returncode == 0:
            print('[TVHandler] Pushed lock.html (legacy HTML lock)')
        else:
            err = (r2.stderr or r2.stdout or b'').decode('utf-8', errors='ignore') if isinstance(r2.stderr, bytes) else r2.stderr or r2.stdout or ''
            print(f'[TVHandler] WARNING: lock.html push failed: {err[:200]}')
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
def _lock_via_legacy_html(adb_path: str, device: str) -> bool:
    """Eski usul: file:// yoki HTTP brauzer — Android 10+ da file:///sdcard ko\'pincha ERR_ACCESS_DENIED.\n    Faqat muhit o\'zgaruvchisi CONTROLPS_LEGACY_HTML_LOCK=1 bo\'lganda chaqiriladi."""
    file_uri = 'file:///sdcard/lock.html'
    file_attempts = [
        ['am', 'start', '--user', '0', '-n', 'com.android.htmlviewer/com.android.htmlviewer.HTMLViewerActivity', '-a', 'android.intent.action.VIEW', '-d', file_uri, '-f', '0x10000000'],
        ['am', 'start', '--user', '0', '-n', 'com.android.htmlviewer/com.android.htmlviewer.HTMLViewerActivity', '-a', 'android.intent.action.VIEW', '-d', file_uri, '-t', 'text/html', '-f', '0x10000000'],
        ['am', 'start', '--user', '0', '-a', 'android.intent.action.VIEW', '-d', file_uri, '-t', 'text/html', '-f', '0x10000000'],
        ['am', 'start', '--user', '0', '-n', 'com.android.browser/com.android.browser.BrowserActivity', '-a', 'android.intent.action.VIEW', '-d', file_uri, '-f', '0x10000000'],
        ['am', 'start', '--user', '0', '-n', 'com.google.android.apps.chrome/com.google.android.apps.chrome.Main', '-a', 'android.intent.action.VIEW', '-d', file_uri, '-f', '0x10000000'],
    ]
    for cmd_parts in file_attempts:
        full_cmd = [adb_path, '-s', device, 'shell'] + cmd_parts
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=6, creationflags=CREATE_NO_WINDOW)
        if _am_start_succeeded(result):
            print('[TVHandler] Lock opened via file:// HTML/view intent')
            return True
    _ensure_http_server()
    lock_url = f'http://{_get_local_ip()}:8099/lock.html'
    htmlviewer_http_cmd = ['am', 'start', '--user', '0', '-n', 'com.android.htmlviewer/com.android.htmlviewer.HTMLViewerActivity', '-a', 'android.intent.action.VIEW', '-d', lock_url, '-t', 'text/html', '-f', '0x10000000']
    hv_http = subprocess.run([adb_path, '-s', device, 'shell'] + htmlviewer_http_cmd, capture_output=True, text=True, timeout=6, creationflags=CREATE_NO_WINDOW)
    if _am_start_succeeded(hv_http):
        print(f'[TVHandler] Lock screen opened via HTMLViewer + HTTP: {lock_url}')
        return True
    else:
        http_bases = [['am', 'start', '--user', '0', '-a', 'android.intent.action.VIEW', '-d', lock_url, '-f', '0x10000000'], ['am', 'start', '--user', '0', '-a', 'android.intent.action.VIEW', '-d', lock_url, '-t', 'text/html', '-f', '0x10000000']]
        http_packages = ('com.android.htmlviewer', 'com.android.tv', 'com.google.android.tv', 'com.tcl.browser', 'com.android.browser', 'org.droidtv.browser', 'org.mozilla.tv.firefox', 'com.amazon.cloud9', 'com.sec.android.app.sbrowser', 'com.google.android.apps.chrome')
        for base in http_bases:
            full_cmd = [adb_path, '-s', device, 'shell'] + base
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=6, creationflags=CREATE_NO_WINDOW)
            if _am_start_succeeded(result):
                print(f'[TVHandler] Lock screen opened from URL: {lock_url}')
                return True
        for pkg in http_packages:
            cmd_parts = ['am', 'start', '--user', '0', '-a', 'android.intent.action.VIEW', '-d', lock_url, '-p', pkg, '-f', '0x10000000']
            full_cmd = [adb_path, '-s', device, 'shell'] + cmd_parts
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=6, creationflags=CREATE_NO_WINDOW)
            if _am_start_succeeded(result):
                print(f'[TVHandler] Lock URL opened with package {pkg}')
                return True
        return False
def _am_start_succeeded(result: subprocess.CompletedProcess) -> bool:
    """am start chiqishi: intent ochilmagan bo\'lsa False (TV toast: ilova yo\'q)."""
    if result.returncode != 0:
        return False
    else:
        text = f"{result.stdout or ''}\n{result.stderr or ''}"
        low = text.lower()
        failures = ('unable to resolve intent', 'unable to find explicit activity', 'no activity found to handle', 'error: activity not started', 'error type 3', 'does not exist.', 'unknown activity')
        return not any((s in low for s in failures))
def _normalize_mac(mac: str) -> str:
    """MAC ni AA:BB:CC:DD:EE:FF ko\'rinishiga keltirish (AABBCCDDEEFF ham qabul)."""
    from app.tv import vidaa_platform
    normalized = vidaa_platform.normalize_mac(mac or '')
    if re.match('^([0-9A-F]{2}:){5}[0-9A-F]{2}$', normalized):
        return normalized
    try:
        mac = (mac or '').strip().upper().replace('-', ':')
        if re.match('^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac):
            return mac
        raw = re.sub('[^0-9A-F]', '', mac)
        if len(raw) == 12:
            return ':'.join((raw[i:i + 2] for i in range(0, 12, 2)))
        return ''
    except Exception:
        return ''
def _adb_shell(adb_path: str, device: str, *shell_args: str, timeout: float=5) -> subprocess.CompletedProcess:
    return subprocess.run([adb_path, '-s', device, 'shell'] + list(shell_args), capture_output=True, text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
def _passthrough_uri_from_input_id(input_id: str) -> str:
    """TvInput id -> content://android.media.tv/passthrough/... URI."""
    if input_id.startswith('content://'):
        return input_id
    else:
        return 'content://android.media.tv/passthrough/' + input_id.replace('/', '%2F')
def _is_hdmi_tv_input_id(input_id: str) -> bool:
    """Faqat haqiqiy HDMI TvInput (tuner/antenna emas)."""
    low = (input_id or '').lower()
    if not low:
        return False
    else:
        if '.tuner.' in low or 'tunerinputservice' in low:
            return False
        else:
            if '.composite.' in low or 'compositeinputservice' in low:
                return False
            else:
                return '.hdmi.' in low or 'hdmiinputservice' in low or '/hdmi' in low
def _parse_hdmi_ports_from_dumpsys(text: str) -> dict[int, str]:
    """dumpsys tv_input dan {hdmi_port_1..4: TvInput id} xaritasi."""
    ports = {}
    if not text:
        return ports
    else:
        hw_to_input = {}
        for m in re.finditer('^\\s*(\\d+):\\s*(com\\.mediatek\\.tvinput/\\.hdmi\\.HDMIInputService/HW\\d+)', text, re.MULTILINE):
            hw_to_input[int(m.group(1))] = m.group(2).strip()
        for m in re.finditer('TvInputHardwareInfo\\s*\\{id=(\\d+)[^}]*hdmi_port=(\\d+)', text, re.IGNORECASE):
            hw_id = int(m.group(1))
            port = int(m.group(2))
            if 1 <= port <= 4:
                if hw_id in hw_to_input:
                    ports[port] = hw_to_input[hw_id]
    if re.search('HDMIInputService/HDMI100004', text):
        if 1 not in ports:
            ports[1] = 'com.mediatek.tvinput/.hdmi.HDMIInputService/HDMI100004'
    for m in re.finditer('content://android\\.media\\.tv/passthrough/([^\\s\'\\\"\\)]+)', text, re.IGNORECASE):
        segment = m.group(1)
        input_id = segment.replace('%2F', '/').replace('%2f', '/')
        if not _is_hdmi_tv_input_id(input_id):
            continue
        window = text[max(0, m.start() - 500):m.end() + 200]
        pm = re.search('hdmi_port[=:](\\d+)', window, re.IGNORECASE)
        if pm:
            p = int(pm.group(1))
            if 1 <= p <= 4:
                    ports[p] = input_id
    for block in re.split('TvInputInfo\\{', text):
        im = re.search('\\bid=([^,\\s}]+)', block)
        if not im:
            continue
        input_id = im.group(1).strip()
        if not _is_hdmi_tv_input_id(input_id):
            continue
        pm = re.search('hdmi_port[=:](\\d+)', block, re.IGNORECASE)
        if pm:
            p = int(pm.group(1))
            if 1 <= p <= 4:
                    ports[p] = input_id
    for m in re.finditer('hdmi_port[=:](\\d+)', text, re.IGNORECASE):
        p = int(m.group(1))
        if not 1 <= p <= 4 or p in ports:
            continue
        window = text[m.start():m.start() + 600]
        im = re.search('\\bid=([^,\\s}]*(?:hdmi|HDMI)[^,\\s}]*?/HW\\d+)', window, re.IGNORECASE)
        if im and _is_hdmi_tv_input_id(im.group(1).strip()):
            ports[p] = im.group(1).strip()
    if not ports:
        ordered = []
        for im in re.finditer('\\bid=([^,\\s}]*(?:hdmi|HDMI|Hdmi)[^,\\s}]*?/HW\\d+)', text, re.IGNORECASE):
            inp = im.group(1).strip()
            if not _is_hdmi_tv_input_id(inp) or inp in ordered:
                continue
            else:
                ordered.append(inp)
        for idx, inp in enumerate(ordered[:4], start=1):
            ports[idx] = inp
    return ports
_hdmi_ports_cache: dict[str, tuple[float, dict[int, str]]] = {}
_HDMI_PORTS_CACHE_TTL_S = 180.0
def _discover_hdmi_ports(adb_path: str, device: str) -> dict[int, str]:
    """TV dagi HDMI portlarini ADB orqali aniqlash."""
    now = time.time()
    cached = _hdmi_ports_cache.get(device)
    if cached and now - cached[0] < _HDMI_PORTS_CACHE_TTL_S and cached[1]:
        return cached[1]
    else:
        merged = ''
        for args in [('dumpsys', 'tv_input'), ('dumpsys', 'activity', 'starter'), ('dumpsys', 'hdmi_control')]:
            try:
                r = _adb_shell(adb_path, device, *args, timeout=10)
                merged += (r.stdout or '') + '\n' + (r.stderr or '') + '\n'
            except Exception:
                continue
        found = _parse_hdmi_ports_from_dumpsys(merged)
        if found:
            _hdmi_ports_cache[device] = (now, found)
            print(f'[TVHandler] HDMI ports discovered: {found}')
        return found
_HDMI_PASSTHROUGH_ACTIVITIES = ('com.smartdevice.livetv/skyworth.skyworthlivetv.osd.ui.mainActivity.LiveTvScreenActivity', 'com.mediatek.wwtv.tvcenter/com.mediatek.wwtv.tvcenter.nav.TurnkeyUiMainActivity', 'org.droidtv.playtv/.PlayTvActivity', 'com.tcl.tv/.TVActivity', 'com.tcl.tv/.MainActivity', 'com.google.android.tv/.MainActivity', 'com.hisense.tv/.MainActivity', 'com.xiaomi.mitv.tvplayer/.TvPlayerActivity')
_TCL_PASSTHROUGH_IDS = {1: 'content://com.tcl.tvpassthrough/.TvPassThroughService/HDMI100004', 2: 'content://com.tcl.tvpassthrough/.TvPassThroughService/HDMI100005', 3: 'content://com.tcl.tvpassthrough/.TvPassThroughService/HDMI100006', 4: 'content://com.tcl.tvpassthrough/.TvPassThroughService/HDMI100007'}
_MEDIATEK_HW_BASE = 4
def _overlay_lock_visible(adb_path: str, device: str) -> bool:
    """Faqat overlay oyna (LockOverlayService) — LockActivity emas."""
    try:
        r = _adb_shell(adb_path, device, 'dumpsys', 'window', timeout=6)
        text = (r.stdout or '') + (r.stderr or '')
        if CONTROLPS_LOCK_PACKAGE not in text:
            return False
        for line in text.splitlines():
            if 'Window{' not in line or CONTROLPS_LOCK_PACKAGE not in line:
                continue
            if 'LockActivity' in line:
                continue
            if 'LockOverlay' in line:
                return True
            low = line.lower()
            if 'overlay' in low and CONTROLPS_LOCK_PACKAGE in line:
                return True
        return False
    except Exception:
        return False
def _lock_activity_focused(adb_path: str, device: str) -> bool:
    try:
        r = _adb_shell(adb_path, device, 'dumpsys', 'window', timeout=5)
        text = (r.stdout or '') + (r.stderr or '')
        for line in text.splitlines():
            return ('mCurrentFocus' in line or 'mFocusedApp' in line) and CONTROLPS_LOCK_PACKAGE in line and ('LockActivity' in line)
    except Exception:
        pass
    return False
def _ensure_controlps_lock_installed(adb_path: str, device: str) -> bool:
    """ControlPS Lock APK o\'rnatilganligini ta\'minlash."""
    apk_path = _get_lock_apk_path()
    check = subprocess.run([adb_path, '-s', device, 'shell', 'pm', 'path', CONTROLPS_LOCK_PACKAGE], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
    if check.returncode == 0 and CONTROLPS_LOCK_PACKAGE in (check.stdout or ''):
            return True
    if not apk_path.exists():
        print(f'[TVHandler] controlps-lock.apk topilmadi: {apk_path}')
        return False
    else:
        print(f'[TVHandler] ControlPS Lock o\'rnatilmoqda: {apk_path}')
        install = subprocess.run([adb_path, '-s', device, 'install', '-r', str(apk_path)], capture_output=True, text=True, timeout=90, creationflags=CREATE_NO_WINDOW)
        ok = install.returncode == 0 and 'Success' in (install.stdout or '')
        if not ok:
            print(f"[TVHandler] APK o\'rnatilmadi: {(install.stderr or install.stdout or '')[:200]}")
        return ok
def _ensure_lock_overlay_permission(adb_path: str, device: str) -> None:
    """Overlay ruxsati (PS ustida blok uchun) — bir marta ADB orqali."""
    _adb_shell(adb_path, device, 'appops', 'set', CONTROLPS_LOCK_PACKAGE, 'SYSTEM_ALERT_WINDOW', 'allow', timeout=5)
    _adb_shell(adb_path, device, 'pm', 'grant', CONTROLPS_LOCK_PACKAGE, 'android.permission.SYSTEM_ALERT_WINDOW', timeout=5)
def _prepare_tv_for_overlay_block(adb_path: str, device: str) -> None:
    """Overlay blok: faqat uyg\'otish — HOME yuborilmaydi (YouTube/PS o\'z joyida qoladi)."""
    _adb_shell(adb_path, device, 'settings', 'put', 'secure', 'screensaver_enabled', '0', timeout=4)
    _adb_shell(adb_path, device, 'input', 'keyevent', '224', timeout=3)
    for pkg in ['com.google.android.apps.tv.dreamx', 'com.android.dreams.basic']:
        _adb_shell(adb_path, device, 'am', 'force-stop', pkg, timeout=3)
    time.sleep(0.2)
def _prepare_tv_for_block(adb_path: str, device: str) -> None:
    """Legacy to\'liq ekran blok: uyg\'otish + bosh ekran (faqat HDMI_PRESERVE_BLOCK o\'chiq bo\'lsa)."""
    _prepare_tv_for_overlay_block(adb_path, device)
    _adb_shell(adb_path, device, 'input', 'keyevent', '3', timeout=3)
    time.sleep(0.35)
def _lock_ui_active(adb_path: str, device: str) -> bool:
    """Blok (overlay yoki LockActivity) hozir ko\'rinadimi."""
    if _overlay_lock_visible(adb_path, device):
        return True
    else:
        try:
            w = _adb_shell(adb_path, device, 'dumpsys', 'window', timeout=5)
            text = (w.stdout or '') + (w.stderr or '')
            for line in text.splitlines():
                if ('mCurrentFocus' in line or 'mFocusedApp' in line) and CONTROLPS_LOCK_PACKAGE in line:
                    return True
        except Exception:
            pass
        return False
def _clear_stale_lock_activity(adb_path: str, device: str) -> None:
    """Eski LockActivity (bosh ekran) yopiladi — overlay uchun joy tayyorlanadi. HOME yuborilmaydi."""
    if not _lock_activity_focused(adb_path, device):
        return
    else:
        print('[TVHandler] Eski LockActivity yopilmoqda (overlay uchun)')
        _adb_shell(adb_path, device, 'am', 'force-stop', CONTROLPS_LOCK_PACKAGE, timeout=5)
        time.sleep(0.35)
def _show_hdmi_overlay_lock(adb_path: str, device: str, *, fast: bool=False, skip_asset_push: bool=False) -> bool:
    """Joriy ekran ustida TORNADO overlay (bosh ekranga o\'tmasdan)."""
    if not fast and (not _ensure_controlps_lock_installed(adb_path, device)):
            return False
    if fast:
        check = subprocess.run([adb_path, '-s', device, 'shell', 'pm', 'path', CONTROLPS_LOCK_PACKAGE], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
        if check.returncode != 0 or CONTROLPS_LOCK_PACKAGE not in (check.stdout or ''):
            return False
    _clear_stale_lock_activity(adb_path, device)
    _prepare_tv_for_overlay_block(adb_path, device)
    _ensure_lock_overlay_permission(adb_path, device)
    if not skip_asset_push:
        _push_lock_screen_assets_to_tv(adb_path, device, push_html=False)
    svc = f'{CONTROLPS_LOCK_PACKAGE}/.LockOverlayService'
    receiver = f'{CONTROLPS_LOCK_PACKAGE}/.OverlayReceiver'
    attempts = [['am', 'startforegroundservice', '-n', svc, '-a', LOCK_OVERLAY_SHOW_ACTION], ['am', 'broadcast', '-n', receiver, '-a', LOCK_OVERLAY_SHOW_ACTION], ['am', 'broadcast', '-a', LOCK_OVERLAY_SHOW_ACTION, '-p', CONTROLPS_LOCK_PACKAGE]]
    wait_s = 0.35 if fast else 0.65
    for attempt_idx, cmd in enumerate(attempts, start=1):
        _adb_shell(adb_path, device, *cmd, timeout=6 if fast else 10)
        time.sleep(wait_s)
        if _overlay_lock_visible(adb_path, device):
            print('[TVHandler] TORNADO overlay shown (joriy ekran saqlanadi)')
            return True
        else:
            if not fast and attempt_idx == 1:
                    _ensure_lock_overlay_permission(adb_path, device)
    return False
def _decode_passthrough_segment(segment: str) -> str:
    """%2F kodlangan TvInput id -> com.foo/.bar/HW5"""
    seg = (segment or '').strip().replace('%2F', '/').replace('%2f', '/')
    if seg.startswith('com.') or seg.startswith('content://'):
        return seg
    else:
        if '/' not in seg and seg.upper().startswith('HW'):
            return f'com.mediatek.tvinput/.hdmi.HDMIInputService/{seg}'
        else:
            return seg
def _capture_tv_resume_state(adb_path: str, device: str) -> dict:
    """STOP dan oldin TV qayerda turganini saqlash (menyu / YouTube / PS HDMI)."""
    state = {'v': 1, 'kind': 'unknown', 'package': '', 'component': '', 'input_id': '', 'passthrough_uri': ''}
    merged_parts = []
    for args in [('dumpsys', 'activity', 'activities'), ('dumpsys', 'activity', 'starter'), ('dumpsys', 'window'), ('dumpsys', 'tv_input')]:
        try:
            r = _adb_shell(adb_path, device, *args, timeout=10)
            merged_parts.append(r.stdout or '')
            merged_parts.append(r.stderr or '')
        except Exception:
            continue
    merged = '\n'.join(merged_parts)
    def _apply_hdmi_input(input_id: str) -> bool:
        if not _is_hdmi_tv_input_id(input_id):
            return False
        else:
            state['kind'] = 'hdmi'
            state['input_id'] = input_id
            state['passthrough_uri'] = _passthrough_uri_from_input_id(input_id)
            return True
    for line in merged.splitlines():
        if not any((token in line for token in ['topResumedActivity', 'mResumedActivity', 'ResumedActivity', 'mCurrentFocus'])):
            continue
        else:
            for pattern in ['dat=content://android\\.media\\.tv/passthrough/([^\\s\'\\\"\\)\\]]+)', 'content://android\\.media\\.tv/passthrough/([^\\s\'\\\"\\)\\]]+)']:
                m = re.search(pattern, line, re.IGNORECASE)
                if m and _apply_hdmi_input(_decode_passthrough_segment(m.group(1))):
                        break
            if state['kind'] == 'hdmi':
                break
    if state['kind'] != 'hdmi':
        for pattern in ['dat=content://android\\.media\\.tv/passthrough/([^\\s\'\\\"\\)\\]]+)', 'content://android\\.media\\.tv/passthrough/([^\\s\'\\\"\\)\\]]+)']:
            m = re.search(pattern, merged, re.IGNORECASE)
            if not m:
                continue
            else:
                if _apply_hdmi_input(_decode_passthrough_segment(m.group(1))):
                    break
    if state['kind'] != 'hdmi':
        for m in re.finditer('inputId:\\s*(\\S+)', merged):
            if _apply_hdmi_input(m.group(1).strip()):
                break
    skip_packages = (CONTROLPS_LOCK_PACKAGE, 'com.android.systemui')
    for line in merged.splitlines():
        if not any((token in line for token in ['topResumedActivity', 'mResumedActivity', 'ResumedActivity', 'mCurrentFocus', 'mFocusedApp'])):
            continue
        else:
            if any((skip in line for skip in skip_packages)):
                continue
            else:
                m = re.search('([\\w.]+)/([\\w.$]+)', line)
                if not m:
                    continue
                else:
                    pkg, act = (m.group(1), m.group(2))
                    if pkg == CONTROLPS_LOCK_PACKAGE:
                        continue
                    else:
                        state['package'] = pkg
                        state['component'] = f'{pkg}/{act}'
                        low = pkg.lower()
                        if state['kind'] == 'unknown':
                            if 'youtube' in low:
                                state['kind'] = 'youtube'
                            else:
                                if 'launcher' in low or low in ['com.google.android.tvlauncher', 'com.android.tv.launcher']:
                                    state['kind'] = 'launcher'
                                else:
                                    if 'livetv' in low or 'tvinput' in low or 'droidtv' in low:
                                        state['kind'] = 'livetv'
                                    else:
                                        state['kind'] = 'app'
                        break
    print(f"[TVHandler] Captured TV session: kind={state['kind']}, pkg={state.get('package') or '-'}, hdmi={state.get('input_id') or '-'}")
    return state
def _save_tv_resume_state(adb_path: str, device: str, state: dict) -> None:
    _resume_state_memory[device] = state
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.json') as tf:
            json.dump(state, tf, ensure_ascii=False)
            tmp_path = tf.name
        r = subprocess.run([adb_path, '-s', device, 'push', tmp_path, _RESUME_STATE_REMOTE], capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0:
            print(f"[TVHandler] resume state push warn: {(r.stderr or r.stdout or '')[:120]}")
    except Exception as e:
        print(f'[TVHandler] resume state save: {e}')
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                return
def _load_tv_resume_state(adb_path: str, device: str) -> dict:
    cached = _resume_state_memory.get(device)
    if cached:
        return cached
    try:
        r = _adb_shell(adb_path, device, 'cat', _RESUME_STATE_REMOTE, timeout=6)
        text = (r.stdout or '').strip()
        if text and text.startswith('{'):
            state = json.loads(text)
            _resume_state_memory[device] = state
            return state
    except Exception as e:
        print(f'[TVHandler] resume state load: {e}')
    return {}
def _restore_tv_resume_state(adb_path: str, device: str, state: dict) -> bool:
    """START: STOP paytida saqlangan ekranga qaytish."""
    if not state:
        return False
    uri = (state.get('passthrough_uri') or '').strip()
    input_id = (state.get('input_id') or '').strip()
    if _is_hdmi_tv_input_id(input_id) or _is_hdmi_tv_input_id(uri):
        target = uri or _passthrough_uri_from_input_id(input_id)
        if _am_start_passthrough_uri(adb_path, device, target):
            print(f'[TVHandler] Restored HDMI session: {input_id or target[:70]}')
            return True
    component = (state.get('component') or '').strip()
    low_comp = component.lower()
    livetv_ui = any((token in low_comp for token in ['wwtv.tvcenter', 'livetv', 'playtv', 'smartdevice.livetv', 'droidtv.playtv']))
    skip_restore_ui = livetv_ui or any((token in low_comp for token in ['com.android.tv.settings', 'com.android.settings', 'tvlauncher', 'launcher']))
    if component and CONTROLPS_LOCK_PACKAGE not in component and (not skip_restore_ui):
        r = _adb_shell(adb_path, device, 'am', 'start', '--user', '0', '-n', component, '-f', '0x14000000', timeout=8)
        if _am_start_succeeded(r):
            print(f'[TVHandler] Restored activity: {component}')
            return True
    package = (state.get('package') or '').strip()
    if package and CONTROLPS_LOCK_PACKAGE not in package:
            for cmd in [['am', 'start', '--user', '0', '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER', '-p', package, '-f', '0x10000000'], ['monkey', '-p', package, '-c', 'android.intent.category.LAUNCHER', '1']]:
                r = _adb_shell(adb_path, device, *cmd, timeout=8)
                out = f"{r.stdout or ''}\n{r.stderr or ''}"
                if _am_start_succeeded(r) or (r.returncode == 0 and 'events injected' in out.lower()):
                    print(f'[TVHandler] Restored app: {package}')
                    return True
    kind = state.get('kind', '')
    if kind == 'launcher':
        _adb_shell(adb_path, device, 'input', 'keyevent', '3', timeout=4)
        print('[TVHandler] Restored launcher (HOME)')
        return True
    else:
        return False
def _hide_hdmi_overlay_lock(adb_path: str, device: str) -> None:
    svc = f'{CONTROLPS_LOCK_PACKAGE}/.LockOverlayService'
    for cmd in [['am', 'startforegroundservice', '-n', svc, '-a', LOCK_OVERLAY_HIDE_ACTION], ['am', 'startservice', '-n', svc, '-a', LOCK_OVERLAY_HIDE_ACTION], ['am', 'broadcast', '-a', LOCK_OVERLAY_HIDE_ACTION, '-p', CONTROLPS_LOCK_PACKAGE]]:
        _adb_shell(adb_path, device, *cmd, timeout=8)
    time.sleep(0.2)
def _save_screen_brightness(adb_path: str, device: str) -> None:
    try:
        r = _adb_shell(adb_path, device, 'settings', 'get', 'system', 'screen_brightness', timeout=4)
        val = (r.stdout or '').strip()
        if val and val != 'null':
            _saved_screen_brightness[device] = val
    except Exception:
        return None
def _restore_screen_brightness(adb_path: str, device: str) -> None:
    val = _saved_screen_brightness.pop(device, '100')
    _adb_shell(adb_path, device, 'settings', 'put', 'system', 'screen_brightness', val, timeout=4)
def _dismiss_android_lock_ui(adb_path: str, device: str) -> None:
    """Blok oynasini yopish (legacy LockActivity uchun)."""
    _hide_hdmi_overlay_lock(adb_path, device)
    _adb_shell(adb_path, device, 'am', 'force-stop', CONTROLPS_LOCK_PACKAGE, timeout=5)
    for pkg in ['com.android.htmlviewer', 'com.google.android.apps.chrome', 'com.android.browser']:
        _adb_shell(adb_path, device, 'am', 'force-stop', pkg, timeout=3)
    for _ in range(2):
        _adb_shell(adb_path, device, 'input', 'keyevent', '4', timeout=3)
        time.sleep(0.12)
def _hdmi_passthrough_candidates(ports: dict[int, str], hdmi_input: int, brand: str) -> list[str]:
    """Tanlangan HDMI uchun sinanadigan TvInput id / URI ro\'yxati."""
    hdmi_input = max(1, min(4, hdmi_input))
    out = []
    seen = set()
    def add(item: str) -> None:
        item = (item or '').strip()
        if not item or item in seen:
            return None
        else:
            seen.add(item)
            out.append(item)
    for port_num, inp in sorted(ports.items()):
        if port_num == hdmi_input and _is_hdmi_tv_input_id(inp):
                add(inp)
    ordered = [inp for _, inp in sorted(ports.items()) if _is_hdmi_tv_input_id(inp)]
    if hdmi_input <= len(ordered):
        add(ordered[hdmi_input - 1])
    for inp in ordered:
        add(inp)
    if brand == 'tcl' and hdmi_input in _TCL_PASSTHROUGH_IDS:
            add(_TCL_PASSTHROUGH_IDS[hdmi_input])
    hw = _MEDIATEK_HW_BASE + hdmi_input
    add(f'com.mediatek.tvinput/.hdmi.HDMIInputService/HW{hw}')
    add(f'com.mediatek.tvinput/.hdmi.HDMIInputService/HW{hdmi_input}')
    return out
def _am_start_passthrough_uri(adb_path: str, device: str, uri: str) -> bool:
    base = ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', uri, '-f', '0x14000000']
    r = _adb_shell(adb_path, device, *base, timeout=8)
    if _am_start_succeeded(r):
        return True
    else:
        for activity in _HDMI_PASSTHROUGH_ACTIVITIES:
            r = _adb_shell(adb_path, device, *base, '-n', activity, timeout=8)
            if _am_start_succeeded(r):
                print(f'[TVHandler] passthrough OK via {activity}')
                return True
        return False
def _switch_hdmi_via_passthrough(adb_path: str, device: str, hdmi_input: int, brand: str='') -> bool:
    """TV Input Framework passthrough intent."""
    ports = _discover_hdmi_ports(adb_path, device)
    for input_id in _hdmi_passthrough_candidates(ports, hdmi_input, brand):
        uri = _passthrough_uri_from_input_id(input_id)
        if _am_start_passthrough_uri(adb_path, device, uri):
            print(f'[TVHandler] HDMI {hdmi_input} passthrough: {input_id}')
            return True
    return False
def _hdmi_keyevent_codes(hdmi_input: int) -> list[str]:
    """Faqat tanlangan HDMI uchun asosiy kod — tez va aniq."""
    hdmi_input = max(1, min(4, hdmi_input))
    return [str(242 + hdmi_input), f'KEYCODE_TV_INPUT_HDMI_{hdmi_input}']
def _switch_hdmi_via_keyevents(adb_path: str, device: str, hdmi_input: int) -> bool:
    """Birinchi asosiy HDMI kodini yuborish — kechikish kam."""
    codes = _hdmi_keyevent_codes(hdmi_input)
    if codes:
        _adb_shell(adb_path, device, 'input', 'keyevent', codes[0], timeout=3)
        time.sleep(0.2)
    print(f'[TVHandler] HDMI {hdmi_input} keyevents sent')
    return True
def _switch_hdmi_via_input_menu(adb_path: str, device: str, hdmi_input: int) -> bool:
    """Manbalar menyusi + raqam tugmalari."""
    for opener in ['178', 'KEYCODE_TV_INPUT', '186', 'KEYCODE_PROG_BLUE']:
        _adb_shell(adb_path, device, 'input', 'keyevent', opener, timeout=4)
        time.sleep(1.0)
        for _ in range(max(0, hdmi_input - 1)):
            _adb_shell(adb_path, device, 'input', 'keyevent', '22', timeout=3)
            time.sleep(0.25)
        _adb_shell(adb_path, device, 'input', 'keyevent', '66', timeout=3)
        time.sleep(0.2)
        num_key = str(7 + hdmi_input)
        _adb_shell(adb_path, device, 'input', 'keyevent', num_key, timeout=3)
        time.sleep(0.3)
    print(f'[TVHandler] HDMI {hdmi_input} input-menu attempts done')
    return True
def _switch_hdmi_via_shell_tune(adb_path: str, device: str, hdmi_input: int) -> bool:
    """Android 11+ cmd tv (mavjud bo\'lsa)."""
    for template in [f'cmd tv tune hdmi {hdmi_input}', f'cmd tv input tune hdmi {hdmi_input}']:
        r = _adb_shell(adb_path, device, 'sh', '-c', template, timeout=5)
        out = ((r.stdout or '') + (r.stderr or '')).lower()
        if r.returncode == 0 and 'unknown command' not in out and ('error' not in out[:80]):
            print(f'[TVHandler] HDMI {hdmi_input} via {template}')
            return True
    return False
def _switch_android_hdmi(adb_path: str, device: str, hdmi_input: int, brand: str='') -> bool:
    """PS (HDMI) ga qaytish — avval blok oynani yopiladi."""
    hdmi_input = max(1, min(4, int(hdmi_input or 1)))
    brand = (brand or '').lower()
    print(f"[TVHandler] Switch to HDMI {hdmi_input} (brand={brand or 'android'})")
    _dismiss_android_lock_ui(adb_path, device)
    time.sleep(0.15)
    _adb_shell(adb_path, device, 'input', 'keyevent', '224', timeout=3)
    time.sleep(0.1)
    for name, fn in [
        ('passthrough', lambda: _switch_hdmi_via_passthrough(adb_path, device, hdmi_input, brand)),
        ('shell_tune', lambda: _switch_hdmi_via_shell_tune(adb_path, device, hdmi_input)),
        ('keyevent', lambda: _switch_hdmi_via_keyevents(adb_path, device, hdmi_input)),
        ('input_menu', lambda: _switch_hdmi_via_input_menu(adb_path, device, hdmi_input)),
    ]:
        try:
            if fn():
                time.sleep(0.25)
                return True
        except Exception as e:
            print(f'[TVHandler] HDMI method {name} error: {e}')
    print(f"[TVHandler] WARNING: HDMI {hdmi_input} ga o'tilmadi")
    return False
class TVHandler:
    """Har bir stol uchun IP/MAC va brend bo\'yicha TV boshqaruvi."""
    def __init__(self, tv_ip: str, tv_mac: str, brand: str, hdmi_input: int=1) -> None:
        self.tv_ip, self.adb_port = self._parse_tv_address(tv_ip)
        self.tv_mac = _normalize_mac(tv_mac or '')
        self.brand = (brand or 'samsung').lower()
        self.hdmi_input = max(1, min(4, int(hdmi_input or 1)))
    def _is_vidaa(self) -> bool:
        return vidaa_platform.is_vidaa_brand(self.brand)
    def _android_hdmi_key(self) -> str:
        """Android TV HDMI keyevent kodi: 243=HDMI1, 244=HDMI2, 245=HDMI3, 246=HDMI4."""
        return str(242 + self.hdmi_input)
    def _switch_to_configured_hdmi(self, adb_path: str, device: str) -> bool:
        """Sozlamalardagi PS ulangan HDMI portiga o\'tish."""
        return _switch_android_hdmi(adb_path, device, self.hdmi_input, self.brand)
    def _samsung_hdmi_key(self) -> str:
        return f'KEY_HDMI{self.hdmi_input}'
    @staticmethod
    def _parse_tv_address(tv_ip: str) -> tuple[str, int]:
        """TV IP maydonida Android ADB porti ham yozilishi mumkin: 192.168.1.10:44021."""
        raw = (tv_ip or '').strip()
        if not raw:
            return ('', 5555)
        host, sep, port_text = raw.rpartition(':')
        if sep and host and port_text.isdigit():
            port = int(port_text)
            if 1 <= port <= 65535:
                    return (host.strip(), port)
        return (raw, 5555)
    def _ensure_adb_connected(self) -> bool:
        """ADB ulanishini ta\'minlash (retry bilan, 25s kesh)."""
        if not self.tv_ip:
            return False
        else:
            port = self.adb_port
            cache_key = f'{self.tv_ip}:{port}'
            if time.time() < _adb_connect_cache.get(cache_key, 0):
                return True
            else:
                adb_path = _get_adb_path()
                for attempt in range(2):
                    res = subprocess.run([adb_path, 'connect', f'{self.tv_ip}:{port}'], capture_output=True, text=True, timeout=4, creationflags=CREATE_NO_WINDOW)
                    out = (res.stdout or '').lower()
                    if 'connected' in out or 'already connected' in out:
                        _adb_connect_cache[cache_key] = time.time() + 25
                        return True
                    else:
                        time.sleep(0.4)
                return False
    def _adb_tcp_port_listening(self, timeout: float=0.5) -> bool:
        """Tarmoqda ADB porti ochiq-yuqligini tez tekshirish (baza default \'samsung\' + Android IP holati)."""
        if not self.tv_ip:
            return False
        try:
            with socket.create_connection((self.tv_ip, self.adb_port), timeout=timeout):
                pass
            return True
        except OSError:
            return False
    def wake_if_possible(self) -> None:
        """MAC bo\'lsa, tarmoq orqali yoqishga urinadi."""
        if not self.tv_mac:
            return
        else:
            try:
                import wakeonlan
                wakeonlan.send_magic_packet(self.tv_mac)
                logger.info('Wake-on-LAN yuborildi: %s', self.tv_mac)
            except Exception as e:
                logger.warning('Wake-on-LAN xatolik: %s', e)
    def _is_tv_on(self) -> bool:
        """Tekshirish: TV yoqilganmi? (ADB ulanishi orqali)"""
        if not self.tv_ip or self.brand not in ANDROID_ADB_BRANDS:
            return False
        if not self._ensure_adb_connected():
            return False
        try:
            adb_path = _get_adb_path()
            port = self.adb_port
            result1 = subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'dumpsys', 'power'], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
            output1 = result1.stdout
            result2 = subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'dumpsys', 'display'], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
            output2 = result2.stdout
            print('[TVHandler] === dumpsys power (first 300 chars) ===')
            print(f'{output1[:300]}')
            print('[TVHandler] === dumpsys display (first 300 chars) ===')
            print(f'{output2[:300]}')
            screen_on_indicators = ['mScreenOn=true', 'mScreenState=ON', 'Display.STATE_ON', 'state=ON', 'mInteractive=true']
            combined_output = output1 + output2
            screen_on = any((indicator in combined_output for indicator in screen_on_indicators))
            if 'mScreenOn=false' in output1:
                screen_on = False
            if 'Display.STATE_OFF' in output2:
                screen_on = False
            print(f'[TVHandler] TV screen check result: {screen_on}')
            return screen_on
        except Exception as e:
            print(f'[TVHandler] TV on check error: {e}')
            return False
    def _smart_tv_gate_context(self) -> tuple[str, str]:
        _ensure_http_server()
        host = normalize_tv_host(self.tv_ip)
        return (_get_local_ip(), _gate_url_for_host(host))
    def _smart_tv_lock_browser_url(self) -> str:
        _ensure_http_server()
        return f'http://{_get_local_ip()}:8099/lock.html'
    def power_on(self) -> None:
        """TV yoqish - START bosilganda."""
        print(f'[TVHandler] power_on called: brand={self.brand}, ip={self.tv_ip}')
        if not self.tv_ip:
            print('[TVHandler] ERROR: IP not provided for power_on')
            return
        else:
            if self._is_vidaa():
                host = normalize_tv_host(self.tv_ip)
                print(f'[TVHandler] VIDAA START: WOL + HDMI{self.hdmi_input} {host}')
                if vidaa_platform.power_on(host, self.tv_mac, wait_s=25.0, brand=self.brand):
                    vidaa_platform.set_source(host, self.tv_mac, self.hdmi_input, brand=self.brand)
                return None
            else:
                if self.brand == 'samsung' and self._adb_tcp_port_listening(timeout=0.5):
                    print('[TVHandler] samsung + ADB — Android safe wake (START)')
                    self._artel_safe_wake_to_hdmi()
                    return
                else:
                    if tv_platforms.is_smart_tv_brand(self.brand):
                        host = normalize_tv_host(self.tv_ip)
                        if tv_platforms.is_webos_brand(self.brand):
                            stop_webos_lock_watchdog(host)
                            if self.tv_mac:
                                print(f'[TVHandler] webOS START WOL: {self.tv_mac} ({host})')
                                self.wake_if_possible()
                            if not tv_platforms.webos_port_open(host, timeout=0.35):
                                print(f'[TVHandler] webOS START: TV online kutilmoqda {host}')
                                tv_platforms.webos_wait_until_online(host, timeout_s=10.0)
                        else:
                            if self.tv_mac:
                                print(f'[TVHandler] Smart TV WOL: {self.tv_mac}')
                                self.wake_if_possible()
                        pc_ip, gate_url = self._smart_tv_gate_context()
                        if tv_platforms.is_webos_brand(self.brand):
                            tv_platforms.webos_push_station_config(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=self.hdmi_input, action='idle')
                        tv_platforms.smart_tv_unblock(host, pc_ip=pc_ip, gate_url=gate_url, brand=self.brand, hdmi_input=self.hdmi_input)
                    else:
                        if self.brand == 'samsung':
                            print('[TVHandler] Sending Samsung POWER ON via Wake-on-LAN')
                            self.wake_if_possible()
                        else:
                            if self.brand in ANDROID_ADB_BRANDS:
                                adb_reachable = self._adb_tcp_port_listening(timeout=0.6)
                                if self.tv_mac and (not adb_reachable):
                                    print(f'[TVHandler] ADB port yopiq — Wake-on-LAN: {self.tv_mac}')
                                    self.wake_if_possible()
                                else:
                                    if self.tv_mac and adb_reachable:
                                            print('[TVHandler] ADB port ochiq — WOL o\'tkazildi (toggle xavfisiz)')
                                self._artel_resume_playstation()
                            else:
                                logger.warning('Noma\'lum brand: %s', self.brand)
                                print(f'[TVHandler] Unknown brand: {self.brand}')
    def power_off(self) -> None:
        """Vaqt tugaganda yoki Stop: TV ni o\'chirmasdan bloklash."""
        print(f'[TVHandler] power_off called: brand={self.brand}, ip={self.tv_ip}')
        if not self.tv_ip:
            print('[TVHandler] ERROR: IP not provided for power_off')
            return
        else:
            if self._is_vidaa():
                host = normalize_tv_host(self.tv_ip)
                print(f'[TVHandler] VIDAA STOP: power off {host}')
                vidaa_platform.power_off(host, self.tv_mac, brand=self.brand)
            else:
                if tv_platforms.is_smart_tv_brand(self.brand):
                    host = normalize_tv_host(self.tv_ip)
                    if tv_platforms.is_webos_brand(self.brand) and tv_platforms.WEBOS_POWER_OFF_ON_STOP:
                        stop_webos_lock_watchdog(host)
                        pc_ip, gate_url = self._smart_tv_gate_context()
                        print(f'[TVHandler] webOS power_off → TV o\'chirish: {host}')
                        tv_platforms.webos_power_off(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=self.hdmi_input)
                    else:
                        print(f'[TVHandler] Smart TV power_off → block_screen ({self.brand})')
                        self.block_screen()
                    return None
                else:
                    if self.brand == 'samsung':
                        print('[TVHandler] Samsung power_off → block_screen (TV o\'chmasin)')
                        self.block_screen()
                        return
                    else:
                        if self.brand in ANDROID_ADB_BRANDS:
                            print(f'[TVHandler] Android TV power_off redirected to block_screen for {self.brand}')
                            self.block_screen()
                            return
                        else:
                            logger.warning('Noma\'lum brand: %s', self.brand)
                            print(f'[TVHandler] Unknown brand: {self.brand}')
    def block_screen(self, *, quick: bool=False) -> None:
        """Ekranni bloklash - STOP: lock.html / ControlPS Lock fon (lock_screen_bg.png), TV o\'chmaydi."""
        print(f'[TVHandler] block_screen called: brand={self.brand}, ip={self.tv_ip}, quick={quick}')
        if not self.tv_ip:
            print('[TVHandler] ERROR: IP not provided for block_screen')
            return
        else:
            if self._is_vidaa():
                host = normalize_tv_host(self.tv_ip)
                print(f'[TVHandler] VIDAA block_screen -> power off {host}')
                vidaa_platform.power_off(host, self.tv_mac, brand=self.brand)
                return
            else:
                if self.brand == 'samsung' and self._adb_tcp_port_listening(timeout=0.5):
                    print('[TVHandler] samsung + ADB — Android bloklash')
                    self._artel_show_message('BLOKLANDI', quick=quick)
                    return
                else:
                    if tv_platforms.is_smart_tv_brand(self.brand):
                        pc_ip, gate_url = self._smart_tv_gate_context()
                        host = normalize_tv_host(self.tv_ip)
                        if tv_platforms.is_webos_brand(self.brand) and tv_platforms.WEBOS_POWER_OFF_ON_STOP:
                            stop_webos_lock_watchdog(host)
                            tv_platforms.webos_power_off(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=self.hdmi_input)
                            return
                        else:
                            lock_params = tv_platforms.build_launch_params(pc_ip, host, gate_url, action='lock', hdmi_input=self.hdmi_input)
                            tv_platforms.smart_tv_block(host, pc_ip=pc_ip, gate_url=gate_url, brand=self.brand, lock_browser_url=self._smart_tv_lock_browser_url(), try_install=not quick)
                            if tv_platforms.is_webos_brand(self.brand):
                                start_webos_lock_watchdog(host, lock_params)
                            return None
                    else:
                        if self.brand in ANDROID_ADB_BRANDS:
                            print('[TVHandler] Blocking Android TV via lock screen')
                            self._artel_show_message('BLOKLANDI', quick=quick)
                            return
                        else:
                            if self.brand == 'samsung':
                                print('[TVHandler] Blocking Samsung TV screen via browser')
                                self._samsung_show_lock_browser()
                            else:
                                logger.warning('Noma\'lum brand: %s', self.brand)
    def _samsung_show_lock_browser(self) -> None:
        from samsungtvws import SamsungTVWS
        if not self.tv_ip:
            return
        try:
            _ensure_http_server()
            ip = _get_local_ip()
            url = f'http://{ip}:8099/lock.html'
            tv = SamsungTVWS(host=self.tv_ip, port=8002)
            tv.open_browser(url)
            logger.info('Samsung TV browser opened: %s', url)
        except Exception as e:
            logger.error('Samsung TV browser error: %s', e)
    def unblock_screen(self) -> None:
        """Ekranni ochish - START: PS (HDMI) ekranida davom etish."""
        print(f'[TVHandler] unblock_screen called: brand={self.brand}, ip={self.tv_ip}')
        if not self.tv_ip:
            print('[TVHandler] ERROR: IP not provided for unblock_screen')
            return
        else:
            if self._is_vidaa():
                host = normalize_tv_host(self.tv_ip)
                print(f'[TVHandler] VIDAA unblock: WOL + HDMI{self.hdmi_input} {host}')
                if vidaa_platform.power_on(host, self.tv_mac, wait_s=25.0, brand=self.brand):
                    vidaa_platform.set_source(host, self.tv_mac, self.hdmi_input, brand=self.brand)
                return None
            else:
                if self.brand == 'samsung' and self._adb_tcp_port_listening(timeout=0.5):
                    print('[TVHandler] samsung + ADB — PS ekraniga qaytish')
                    self._artel_resume_playstation()
                    return
                else:
                    if tv_platforms.is_smart_tv_brand(self.brand):
                        host = normalize_tv_host(self.tv_ip)
                        if tv_platforms.is_webos_brand(self.brand):
                            stop_webos_lock_watchdog(host)
                            if self.tv_mac:
                                print(f'[TVHandler] webOS unblock WOL: {self.tv_mac} ({host})')
                                self.wake_if_possible()
                            if not tv_platforms.webos_port_open(host, timeout=0.35):
                                print(f'[TVHandler] webOS unblock: TV online kutilmoqda {host}')
                                tv_platforms.webos_wait_until_online(host, timeout_s=10.0)
                        pc_ip, gate_url = self._smart_tv_gate_context()
                        if tv_platforms.is_webos_brand(self.brand):
                            tv_platforms.webos_push_station_config(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=self.hdmi_input, action='idle')
                        tv_platforms.smart_tv_unblock(host, pc_ip=pc_ip, gate_url=gate_url, brand=self.brand, hdmi_input=self.hdmi_input)
                    else:
                        if self.brand in ANDROID_ADB_BRANDS:
                            self._artel_resume_playstation()
                        else:
                            if self.brand == 'samsung':
                                print('[TVHandler] Unblocking Samsung TV screen - returning to correct input')
                                self._samsung_send_key(self._samsung_hdmi_key())
                            else:
                                logger.warning('Noma\'lum brand: %s', self.brand)
    def _artel_show_message(self, message: str, *, quick: bool=False) -> None:
        """ADB orqali TV bloklash. Default: HDMI (PS) ustida overlay — bosh ekranga o\'tmaydi."""
        print(f'[TVHandler] _artel_show_message: {message} {self.tv_ip} quick={quick}')
        if not self.tv_ip:
            return
        port = self.adb_port
        adb_path = _get_adb_path()
        device = f'{self.tv_ip}:{port}'
        with _lock_for_device(device):
            if not self._ensure_adb_connected():
                print(f"[TVHandler] WARNING: TV ga ulanib bo'lmadi: {self.tv_ip}:{port}")
                return
            if _overlay_lock_visible(adb_path, device):
                return
            if not quick:
                subprocess.run([adb_path, '-s', device, 'shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
            apk_path = _get_lock_apk_path()
            blocked = False
            if HDMI_PRESERVE_BLOCK:
                if quick:
                    blocked = _show_hdmi_overlay_lock(adb_path, device, fast=True, skip_asset_push=True)
                else:
                    resume_state = _capture_tv_resume_state(adb_path, device)
                    for overlay_round in range(2):
                        if _show_hdmi_overlay_lock(adb_path, device):
                            blocked = True
                            break
                        if overlay_round == 0:
                            _ensure_controlps_lock_installed(adb_path, device)
                            _ensure_lock_overlay_permission(adb_path, device)
                            time.sleep(0.3)
                    if blocked:
                        resume_state['block_mode'] = 'overlay'
                        print('[TVHandler] TORNADO overlay bloklandi (joriy ilova saqlanadi)')
                    else:
                        resume_state['block_mode'] = 'failed_overlay'
                        if not quick:
                            print(f'[TVHandler] WARNING: Overlay blok ochilmadi. TV da:\n  adb install -r "{apk_path}"\n  adb shell appops set uz.controlps.lock SYSTEM_ALERT_WINDOW allow')
                    _save_tv_resume_state(adb_path, device, resume_state)
                return
            try:
                subprocess.run([adb_path, '-s', device, 'shell', 'input', 'keyevent', '3'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                time.sleep(0.5)
                for attempt in range(3):
                    if self._launch_controlps_lock_app(adb_path, port, message):
                        return
                    if attempt < 2 and apk_path.exists():
                        subprocess.run([adb_path, '-s', device, 'install', '-r', str(apk_path)], capture_output=True, text=True, timeout=45, creationflags=CREATE_NO_WINDOW)
                        time.sleep(1.0)
            except Exception as e:
                print(f'[TVHandler] ERROR in _artel_show_message: {e}')
    def _launch_controlps_lock_app(self, adb_path: str, port: int, message: str, *, skip_prepare: bool=False) -> bool:
        """Maxsus Android TV lock APK ni ochish. O\'rnatilmagan bo\'lsa False qaytaradi."""
        apk_path = _get_lock_apk_path()
        device = f'{self.tv_ip}:{port}'
        try:
            if not skip_prepare:
                _prepare_tv_for_block(adb_path, device)
            install_check = subprocess.run([adb_path, '-s', device, 'shell', 'pm', 'path', CONTROLPS_LOCK_PACKAGE], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
            if install_check.returncode != 0 or CONTROLPS_LOCK_PACKAGE not in install_check.stdout:
                if apk_path.exists():
                    print(f'[TVHandler] Installing ControlPS Lock APK: {apk_path}')
                    install_result = subprocess.run([adb_path, '-s', device, 'install', '-r', str(apk_path)], capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
                    if install_result.returncode != 0 or 'Success' not in install_result.stdout:
                        print(f'[TVHandler] ControlPS Lock install failed: {install_result.stderr or install_result.stdout}')
                        return False
                else:
                    print(f'[TVHandler] ControlPS Lock APK not found: {apk_path}')
                    return False
            result = subprocess.run([adb_path, '-s', device, 'shell', 'am', 'start', '--user', '0', '-n', CONTROLPS_LOCK_ACTIVITY, '--es', 'message', message, '-f', '0x14000000'], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            if _am_start_succeeded(result):
                return True
            out1 = f'{result.stdout}\n{result.stderr}'
            if 'brought to the front' in out1.lower():
                return True
            print(f'[TVHandler] ControlPS Lock explicit launch not ok: {out1.strip()[:400]}')
            result2 = subprocess.run([adb_path, '-s', device, 'shell', 'am', 'start', '--user', '0', '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER', '-p', CONTROLPS_LOCK_PACKAGE, '-f', '0x10000000'], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
            if _am_start_succeeded(result2):
                return True
            result3 = subprocess.run([adb_path, '-s', device, 'shell', 'monkey', '-p', CONTROLPS_LOCK_PACKAGE, '-c', 'android.intent.category.LAUNCHER', '1'], capture_output=True, text=True, timeout=8, creationflags=CREATE_NO_WINDOW)
            out3 = f"{result3.stdout or ''}\n{result3.stderr or ''}"
            if result3.returncode == 0 and 'events injected' in out3.lower() and ('no activities' not in out3.lower()):
                return True
            print(f'[TVHandler] ControlPS Lock monkey/launcher failed: {out3.strip()[:400]}')
        except Exception as e:
            print(f'[TVHandler] ControlPS Lock launch error: {e}')
        return False
    def _artel_block_without_browser(self) -> None:
        """Browser yo\'q Android TVlar uchun bloklash: ekran qorayadi yoki sleep holatiga o\'tadi."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', '3'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_brightness', '0'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_off_timeout', '1000'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', 'KEYCODE_SLEEP'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    print('[TVHandler] Android TV blocked without browser')
                except Exception as e:
                    print(f'[TVHandler] ERROR in _artel_block_without_browser: {e}')
    def volume_up(self) -> None:
        """Ovozni balandlatish."""
        if self._is_vidaa():
            vidaa_platform.send_key(normalize_tv_host(self.tv_ip), self.tv_mac, 'KEY_VOLUMEUP', brand=self.brand)
        else:
            if tv_platforms.is_webos_brand(self.brand):
                logger.info('webOS TV: volume_up tugmasi hozircha set_volume orqali boshqariladi')
            else:
                if tv_platforms.is_tizen_brand(self.brand):
                    tv_platforms.smart_tv_volume(normalize_tv_host(self.tv_ip), self.brand, 1)
                else:
                    if self.brand == 'samsung':
                        self._samsung_send_key('KEY_VOLUP')
                    else:
                        if self.brand in ANDROID_ADB_BRANDS:
                            self._artel_send_key('24')
    def volume_down(self) -> None:
        """Ovozni pasaytirish."""
        if self._is_vidaa():
            vidaa_platform.send_key(normalize_tv_host(self.tv_ip), self.tv_mac, 'KEY_VOLUMEDOWN', brand=self.brand)
        else:
            if tv_platforms.is_webos_brand(self.brand):
                logger.info('webOS TV: volume_down tugmasi hozircha set_volume orqali boshqariladi')
            else:
                if tv_platforms.is_tizen_brand(self.brand):
                    tv_platforms.smart_tv_volume(normalize_tv_host(self.tv_ip), self.brand, (-1))
                else:
                    if self.brand == 'samsung':
                        self._samsung_send_key('KEY_VOLDOWN')
                    else:
                        if self.brand in ANDROID_ADB_BRANDS:
                            self._artel_send_key('25')
    def set_volume(self, level: int) -> None:
        """Ovozni aniq qiymatga o\'rnatish (0-100)."""
        level = max(0, min(100, int(level)))
        if self._is_vidaa():
            vidaa_platform.set_volume(normalize_tv_host(self.tv_ip), self.tv_mac, level, brand=self.brand)
        else:
            if tv_platforms.is_webos_brand(self.brand):
                host = normalize_tv_host(self.tv_ip)
                if tv_platforms.webos_port_open(host, timeout=1.0):
                    tv_platforms.webos_set_volume(host, level)
                else:
                    logger.info('webOS TV offline, ovoz faqat bazaga saqlandi: %s -> %s', host, level)
            else:
                if self.brand in ANDROID_ADB_BRANDS:
                    self._artel_set_volume(level)
                else:
                    if self.brand == 'samsung':
                        logger.info('Samsung TV: ovoz %s ga o\'rnatish', level)
                    else:
                        logger.warning('Noma\'lum brand: %s', self.brand)
    def _artel_set_volume(self, level: int) -> None:
        """ADB orqali aniq ovoz qiymatini o\'rnatish - To\'liq 0-100."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                level = max(0, min(100, int(level)))
                try:
                    before = self._artel_get_volume()
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'cmd', 'media_session', 'volume', '--stream', '3', '--set', str(level), '--show'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    time.sleep(0.25)
                    after = self._artel_get_volume()
                    if after is None or abs(after - level) > 1:
                        current = before if before is not None else after
                        if current is not None:
                            self._artel_adjust_volume_with_keys(current, level)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'am', 'broadcast', '-a', 'android.media.VOLUME_CHANGED_ACTION'], capture_output=True, timeout=2, creationflags=CREATE_NO_WINDOW)
                    final = self._artel_get_volume()
                    print(f'[TVHandler] Volume set requested={level}%, before={before}, final={final}')
                    logger.info('ADB volume updated requested=%s%% before=%s final=%s', level, before, final)
                except Exception as e:
                    print(f'[TVHandler] ERROR setting volume: {e}')
                    logger.debug(f'Volume error: {e}')
    def _artel_get_volume(self) -> Optional[int]:
        """Android TV joriy media ovozini 0-100 shkalada o\'qish."""
        if not self.tv_ip:
            return
        else:
            port = self.adb_port
            adb_path = _get_adb_path()
        try:
            result = subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'cmd', 'media_session', 'volume', '--stream', '3', '--get'], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
            match = re.search('volume is\\s+(\\d+)\\s+in range\\s+\\[(\\d+)\\.\\.(\\d+)\\]', result.stdout)
            if match:
                current = int(match.group(1))
                max_value = max(1, int(match.group(3)))
                return round(current * 100 / max_value)
        except Exception as e:
            print(f'[TVHandler] ERROR reading volume: {e}')
        return None
    def _artel_adjust_volume_with_keys(self, current: int, target: int) -> None:
        """To\'g\'ridan-to\'g\'ri set ishlamaydigan TVlarda pult tugmalarini bitta oqimda yuborish."""
        delta = max((-100), min(100, int(target) - int(current)))
        if delta == 0:
            return
        else:
            key = 'KEYCODE_VOLUME_UP' if delta > 0 else 'KEYCODE_VOLUME_DOWN'
            steps = abs(delta)
            port = self.adb_port
            adb_path = _get_adb_path()
            shell_script = f'i=0; while [ \"$i\" -lt {steps} ]; do input keyevent {key}; i=$((i+1)); done'
            subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', shell_script], capture_output=True, timeout=max(5, steps // 4 + 5), creationflags=CREATE_NO_WINDOW)
    def _artel_dim_screen_to_black(self) -> None:
        """Ekran yorug\'ligini 0 ga tushirish - TV o\'chmaydi, faqat ekran qora bo\'ladi."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    result = subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'get', 'system', 'screen_brightness'], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    self._original_brightness = result.stdout.strip() if result.returncode == 0 else '100'
                    result2 = subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'get', 'system', 'screen_off_timeout'], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    self._original_timeout = result2.stdout.strip() if result2.returncode == 0 else '300000'
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_brightness', '0'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_off_timeout', '1800000'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', '224'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    print('[TVHandler] Screen dimmed to black (brightness=0), TV stays on')
                    logger.info('Screen dimmed to black, original brightness=%s', self._original_brightness)
                except Exception as e:
                    print(f'[TVHandler] ERROR dimming screen: {e}')
                    logger.debug(f'Dim screen error: {e}')
    def _artel_restore_screen(self) -> None:
        """Ekran yorug\'ligini qaytarish."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    brightness = getattr(self, '_original_brightness', '100')
                    timeout = getattr(self, '_original_timeout', '300000')
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_brightness', brightness], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_off_timeout', timeout], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', '224'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    print(f'[TVHandler] Screen restored (brightness={brightness})')
                    logger.info('Screen restored to brightness=%s', brightness)
                except Exception as e:
                    print(f'[TVHandler] ERROR restoring screen: {e}')
                    logger.debug(f'Restore screen error: {e}')
    def _samsung_send_key(self, key: str) -> None:
        try:
            from samsungtvws import SamsungTVWS
            if not self.tv_ip:
                logger.warning('Samsung: IP ko\'rsatilmagan')
                return
            else:
                tv = SamsungTVWS(host=self.tv_ip, port=8002)
                tv.send_key(key, 'Click')
                logger.info('Samsung %s yuborildi: %s', key, self.tv_ip)
        except ImportError:
            logger.warning('samsungtvws o\'rnatilmagan: pip install samsungtvws')
        except Exception as e:
            logger.error('Samsung TV xatolik (%s): %s', key, e)
    def _artel_send_key(self, key: str) -> None:
        """ADB orqali keyevent yuborish."""
        print(f'[TVHandler] _artel_send_key: key={key}, ip={self.tv_ip}')
        if not self.tv_ip:
            print('[TVHandler] ERROR: No IP provided')
            return
        else:
            if not self._ensure_adb_connected():
                print(f'[TVHandler] ERROR: Could not connect ADB to {self.tv_ip}')
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                print(f'[TVHandler] Using adb path: {adb_path}')
                try:
                    result = subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', key], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
                    print(f'[TVHandler] ADB result: rc={result.returncode}, stdout={result.stdout[:200]}, stderr={result.stderr[:200]}')
                except FileNotFoundError:
                    print(f'[TVHandler] ERROR: adb command not found at {adb_path}')
                except Exception as e:
                    print(f'[TVHandler] ERROR: {e}')
                    logger.debug('adb CLI xatolik: %s', e)
                else:
                    return
                try:
                    from adb_shell.adb_device import AdbDeviceTcp
                    device = AdbDeviceTcp(self.tv_ip, port, default_transport_timeout_s=5.0)
                    try:
                        device.connect(rsa_keys=None, auth_timeout_s=5.0)
                    except Exception:
                        device.connect(rsa_keys=[], auth_timeout_s=5.0)
                    device.shell(f'input keyevent {key}')
                    logger.info('adb-shell keyevent %s: %s', key, self.tv_ip)
                except ImportError:
                    logger.warning('adb/adb-shell topilmadi.')
                except Exception as e:
                    logger.error('ADB (adb-shell) xatolik (%s): %s', key, e)
    def _artel_block_by_input_switch(self) -> None:
        """Immer TV: boshqa input ga o\'tkazib ekranni bloklash."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', '170'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    print('[TVHandler] Switched to TV input (blocked)')
                except Exception as e:
                    print(f'[TVHandler] ERROR switching input: {e}')
    def _artel_restore_input(self) -> None:
        """Immer TV: HDMI inputiga qaytish."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    self._switch_to_configured_hdmi(adb_path, f'{self.tv_ip}:{port}')
                    print('[TVHandler] Restored to HDMI input')
                except Exception as e:
                    print(f'[TVHandler] ERROR restoring input: {e}')
    def _artel_show_black_screen(self) -> None:
        """Immer TV: screensaver rejimi (qora ekran + soat, pult bilan ochilmaydi)."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'secure', 'screensaver_enabled', '1'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'secure', 'screensaver_components', 'com.android.dreams.basic/com.android.dreams.basic.Colors'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_off_timeout', '1000'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'am', 'broadcast', '-a', 'android.intent.action.DREAMING_STARTED'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'secure', 'doze_pulse_on_pick_up', '0'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    print('[TVHandler] Screensaver enabled (black screen + clock)')
                except Exception as e:
                    print(f'[TVHandler] ERROR enabling screensaver: {e}')
    def _artel_disable_screensaver(self) -> None:
        """Immer TV: screensaver ni o\'chirish va PlayStationga qaytish."""
        if not self.tv_ip:
            return
        else:
            if not self._ensure_adb_connected():
                return
            else:
                port = self.adb_port
                adb_path = _get_adb_path()
                try:
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'secure', 'screensaver_enabled', '0'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'settings', 'put', 'system', 'screen_off_timeout', '300000'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([adb_path, '-s', f'{self.tv_ip}:{port}', 'shell', 'input', 'keyevent', '224'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    import time
                    time.sleep(0.5)
                    self._switch_to_configured_hdmi(adb_path, f'{self.tv_ip}:{port}')
                    print('[TVHandler] Screensaver disabled, returned to PlayStation')
                except Exception as e:
                    print(f'[TVHandler] ERROR disabling screensaver: {e}')
    def _artel_resume_playstation(self) -> None:
        """START: overlay yopiladi — YouTube/PS o\'z joyidan davom etadi (bosh ekranga emas)."""
        if not self.tv_ip:
            return
        if not self._ensure_adb_connected():
            return
        port = self.adb_port
        adb_path = _get_adb_path()
        device = f'{self.tv_ip}:{port}'
        with _lock_for_device(device):
            if HDMI_PRESERVE_BLOCK:
                saved = _load_tv_resume_state(adb_path, device)
                block_mode = (saved.get('block_mode') or '').strip().lower()
                _hide_hdmi_overlay_lock(adb_path, device)
                if block_mode == 'overlay':
                    _restore_screen_brightness(adb_path, device)
                    subprocess.run([adb_path, '-s', device, 'shell', 'input', 'keyevent', '224'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                    print('[TVHandler] START — overlay yopildi, joriy ilova davom etadi')
                    return
                _dismiss_android_lock_ui(adb_path, device)
                _restore_screen_brightness(adb_path, device)
                subprocess.run([adb_path, '-s', device, 'shell', 'input', 'keyevent', '224'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                time.sleep(0.15)
                restored = False
                if saved.get('block_mode') != 'failed_overlay':
                    restored = _restore_tv_resume_state(adb_path, device, saved)
                if restored:
                    print('[TVHandler] START — saqlangan ekranga qaytdi')
                elif self.hdmi_input:
                    self._switch_to_configured_hdmi(adb_path, device)
                    print("[TVHandler] START — sozlangan HDMI portiga o'tildi")
                return
            try:
                _dismiss_android_lock_ui(adb_path, device)
                _restore_screen_brightness(adb_path, device)
                subprocess.run([adb_path, '-s', device, 'shell', 'input', 'keyevent', '224'], capture_output=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                for attempt in range(2):
                    if self._switch_to_configured_hdmi(adb_path, device):
                        break
                    time.sleep(0.4)
            except Exception as e:
                print(f'[TVHandler] ERROR in resume playstation: {e}')
    def _artel_safe_wake_to_hdmi(self) -> None:
        """Eski nom — _artel_resume_playstation ga yo\'naltiriladi."""
        self._artel_resume_playstation()