"""LG webOS va Samsung Tizen TV boshqaruvi (PC tomondan).\n\nTV ilovalari HTTP gate orqali polling qiladi; bu modul tez javob uchun\nilovani ishga tushirish / yopish va ovoz/HDMI yordamchi funksiyalarini beradi.\n"""
from __future__ import annotations
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional
if sys.platform == 'win32':
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    CREATE_NO_WINDOW = 0
logger = logging.getLogger(__name__)
WEBOS_BRANDS = frozenset({'lg', 'webos'})
TIZEN_BRANDS = frozenset({'samsung', 'tizen'})
SMART_TV_BRANDS = WEBOS_BRANDS | TIZEN_BRANDS
WEBOS_APP_ID = 'com.controlps.lock'
TIZEN_APP_ID = 'com.controlps.lock.ControlPSLock'
TIZEN_PACKAGE = 'com.controlps.lock'
WEBOS_IPK_NAME = 'controlps-lock.ipk'
TIZEN_WGT_NAME = 'controlps-lock.wgt'
WEBOS_POWER_OFF_ON_STOP = os.environ.get('CONTROLPS_WEBOS_STOP_MODE', 'poweroff').strip().lower() not in ['block', 'lock', '0', 'false', 'no']
def is_webos_brand(brand: str) -> bool:
    return (brand or '').strip().lower() in WEBOS_BRANDS
def is_tizen_brand(brand: str) -> bool:
    return (brand or '').strip().lower() in TIZEN_BRANDS
def is_smart_tv_brand(brand: str) -> bool:
    b = (brand or '').strip().lower()
    return b in SMART_TV_BRANDS
def _resource_dir() -> Path:
    from app.core.runtime import app_dir
    return app_dir()
_ares_device_cache: dict[str, str] = {}
_ares_host_cache: dict[str, str] = {}
_webos_launch_locks: dict[str, threading.Lock] = {}
_webos_launch_locks_guard = threading.Lock()
_ares_profile_ready = False
def clear_ares_device_cache(host: str='') -> None:
    """IP o\'zgarganda yoki TV qayta ulanganda eski ares keshini tozalash."""
    h = (host or '').split(':', 1)[0].strip()
    if h:
        old_name = _ares_device_cache.pop(h, None)
        if old_name:
            _ares_host_cache.pop(old_name, None)
        return None
    else:
        _ares_device_cache.clear()
        _ares_host_cache.clear()
def _parse_ares_device_hosts(text: str) -> dict[str, str]:
    """ares-setup-device -l chiqishidan {IP: device_name}."""
    mapping = {}
    for line in _strip_ansi(text or '').splitlines():
        m = re.match('^(\\S+)\\s+\\S+@(\\d{1,3}(?:\\.\\d{1,3}){3}):\\d+', line.strip())
        if not m:
            continue
        else:
            name, ip = (m.group(1).strip(), m.group(2).strip())
            if name.lower() in ['name', '---------------']:
                continue
            else:
                mapping[ip] = name
                _ares_host_cache[name] = ip
    return mapping
def list_ares_webos_devices() -> dict[str, str]:
    """{TV_IP: ares_device_name} — ares-setup-device ro\'yxati."""
    prepare_webos_cli()
    ares_cli = _ares_cli_path('ares-setup-device')
    if not ares_cli:
        return {}
    else:
        try:
            res = _run_cmd([ares_cli, '-l'], timeout=12)
            text = (res.stdout or '') + (res.stderr or '')
            return _parse_ares_device_hosts(text)
        except Exception as e:
            logger.debug('list_ares_webos_devices: %s', e)
            return {}
def register_webos_device_mapping(host: str, device_name: str) -> None:
    """webos_devices.json ga IP -> ares nomini yozish."""
    host = (host or '').split(':', 1)[0].strip()
    device_name = (device_name or '').strip()
    if not host or not device_name:
        return None
    else:
        try:
            from app.core.runtime import load_json_config, save_json_config
            data = load_json_config('webos_devices.json', {})
            devices = data.get('devices') if isinstance(data.get('devices'), dict) else data
            if not isinstance(devices, dict):
                devices = {}
            devices[host] = device_name
            save_json_config('webos_devices.json', {'devices': devices})
            _ares_device_cache[host] = device_name
            _ares_host_cache[device_name] = host
            logger.info('webOS mapping saqlandi: %s -> %s', host, device_name)
        except Exception as e:
            logger.warning('webOS mapping saqlanmadi: %s', e)
def sync_webos_device_mappings_from_ares() -> dict[str, str]:
    """ares ro\'yxatidan webos_devices.json ni yangilash."""
    live = list_ares_webos_devices()
    if not live:
        return live
    else:
        try:
            from app.core.runtime import load_json_config, save_json_config
            data = load_json_config('webos_devices.json', {})
            devices = data.get('devices') if isinstance(data.get('devices'), dict) else {}
            if not isinstance(devices, dict):
                devices = {}
            devices.update(live)
            save_json_config('webos_devices.json', {'devices': devices})
            for ip, name in live.items():
                _ares_device_cache[ip] = name
                _ares_host_cache[name] = ip
        except Exception as e:
            logger.warning('webOS mapping sinxron: %s', e)
        return live
def webos_port_open(host: str, port: int=9922, timeout: float=1.2) -> bool:
    """TV webOS SSH porti ochiqmi."""
    host = (host or '').split(':', 1)[0].strip()
    if not host:
        return False
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
def webos_push_station_config(tv_ip: str, *, pc_ip: str, gate_url: str, hdmi_input: int=1, action: str='') -> bool:
    """TV blok ilovasiga to\'g\'ri tv_ip/pc_ip yuborish."""
    host = (tv_ip or '').split(':', 1)[0].strip()
    if not host:
        return False
    else:
        params = build_launch_params(pc_ip, host, gate_url, action=action, hdmi_input=hdmi_input)
        return webos_launch(host, params)
def _run_cmd(args: list[str], *, timeout: float=20, check: bool=False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, creationflags=CREATE_NO_WINDOW, check=check)
def _retry_call(fn, *args, attempts: int=3, delays: tuple[float, ...]=(0.0, 0.5, 1.2), **kwargs) -> bool:
    """webOS ares-launch: tarmoq/seans aralashuvida qayta urinish."""
    for attempt in range(max(1, attempts)):
        if attempt > 0 and attempt - 1 < len(delays):
            time.sleep(delays[attempt - 1])
        try:
            if fn(*args, **kwargs):
                return True
        except Exception as e:
            logger.debug('retry %s attempt %s: %s', getattr(fn, '__name__', fn), attempt + 1, e)
    return False
def build_launch_params(pc_ip: str, tv_ip: str, gate_url: str, action: str='', *, hdmi_input: int=0) -> dict[str, str]:
    params = {'pc_ip': (pc_ip or '').strip(), 'tv_ip': (tv_ip or '').strip(), 'gate_url': (gate_url or '').strip()}
    if action:
        params['action'] = action
    if hdmi_input:
        params['hdmi_input'] = str(max(1, min(4, int(hdmi_input))))
    return params
def _project_tools_dir() -> Path:
    base = _resource_dir()
    for candidate in [base / 'tools', base.parent / 'tools', Path(__file__).resolve().parent / 'tools']:
        if (candidate / 'ares-cli' / 'node_modules').is_dir():
            return candidate
    return base / 'tools'
def _webos_device_map() -> dict[str, str]:
    """webos_devices.json: IP -> ares qurilma nomi (masalan LG2)."""
    try:
        from app.core.runtime import load_json_config
        data = load_json_config('webos_devices.json', {})
        raw = data.get('devices') if isinstance(data.get('devices'), dict) else data
        if not isinstance(raw, dict):
            return {}
        else:
            return {str(k).split(':', 1)[0].strip(): str(v).strip() for k, v in raw.items() if k and v}
    except Exception:
        return {}
def prepare_webos_cli() -> None:
    """ares-cli tv profilini sozlash (exe dist/ dan ishlaganda ham)."""
    global _ares_profile_ready
    if _ares_profile_ready:
        return
    else:
        try:
            from app.core.runtime import ensure_tv_tools_path
            ensure_tv_tools_path()
        except Exception:
            pass
        ares_path = _ares_launch_path()
        if ares_path:
            logger.info('webOS ares-launch: %s', ares_path)
        else:
            logger.warning('webOS ares-launch topilmadi — install_tv_tools.bat (2)')
        ares_config = _ares_cli_path('ares-config')
        if ares_config:
            try:
                _run_cmd([ares_config, '--profile', 'tv'], timeout=8)
            except Exception as e:
                logger.debug('ares-config tv: %s', e)
        _ares_profile_ready = True
def warmup_webos_devices() -> None:
    """Dastur ochilganda TV qurilma nomlarini keshga olish (START/STOP tezroq)."""
    prepare_webos_cli()
    try:
        import database as db
        for sid in db.list_station_ids():
            row = db.get_tv_settings(sid)
            if not is_webos_brand(row.brand):
                continue
            else:
                host = (row.tv_ip or '').split(':', 1)[0].strip()
                if host:
                    _ares_device_for_ip(host)
    except Exception as e:
        logger.debug('warmup_webos_devices: %s', e)
def _local_ares_bin(name: str) -> Path:
    return _project_tools_dir() / 'ares-cli' / 'node_modules' / '.bin' / f'{name}.cmd'
def _local_sdb_paths() -> tuple[str, ...]:
    root = _project_tools_dir()
    return (str(root / 'sdb' / 'sdb.exe'), str(root / 'tizen-sdk' / 'tools' / 'sdb.exe'))
def _find_cli(name: str, extra_paths: tuple[str, ...]=()) -> Optional[str]:
    for p in extra_paths:
        if Path(p).is_file():
            return p
    found = shutil.which(name)
    if found:
        return found
def _ares_cli_path(name: str) -> Optional[str]:
    """ares-launch, ares-install, ares-setup-device, ..."""
    local = _local_ares_bin(name)
    if local.is_file():
        return str(local)
    else:
        appdata = Path(os.environ.get('APPDATA', '')) / 'npm' / f'{name}.cmd'
        if appdata.is_file():
            return str(appdata)
        else:
            return _find_cli(name)
def _ares_launch_path() -> Optional[str]:
    return _ares_cli_path('ares-launch')
def _sdb_path() -> Optional[str]:
    candidates = _local_sdb_paths() + ('C:\\tizen-studio\\tools\\sdb.exe', 'C:\\Tizen Studio\\tools\\sdb.exe', os.path.expandvars('%LOCALAPPDATA%\\Tizen Studio\\tools\\sdb.exe'), os.path.expandvars('%USERPROFILE%\\tizen-studio\\tools\\sdb.exe'))
    return _find_cli('sdb', candidates)
_ANSI_RE = re.compile('\\x1b\\[[0-9;]*m')
def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)
def _ares_device_for_ip(tv_ip: str) -> Optional[str]:
    """ares-setup-device / ares-launch -D ro\'yxatidan IP bo\'yicha qurilma nomini topish."""
    tv_ip = (tv_ip or '').strip()
    if not tv_ip:
        return
    else:
        host = tv_ip.split(':', 1)[0].strip()
        cached = _ares_device_cache.get(host)
        if cached:
            return cached
        else:
            mapped = _webos_device_map().get(host)
            if mapped:
                _ares_device_cache[host] = mapped
                _ares_host_cache[mapped] = host
                logger.info('webOS qurilma (json): %s -> %s', host, mapped)
                return mapped
            else:
                prepare_webos_cli()
                live = list_ares_webos_devices()
                if host in live:
                    name = live[host]
                    _ares_device_cache[host] = name
                    return name
                else:
                    cli_specs = (('ares-setup-device', '-l'), ('ares-launch', '-D'))
                    for cli_name, list_flag in cli_specs:
                        try:
                            ares_cli = _ares_cli_path(cli_name)
                            if not ares_cli:
                                continue
                            res = _run_cmd([ares_cli, list_flag], timeout=10)
                            parsed = _parse_ares_device_hosts((res.stdout or '') + (res.stderr or ''))
                            if host in parsed:
                                name = parsed[host]
                                _ares_device_cache[host] = name
                                register_webos_device_mapping(host, name)
                                return name
                        except Exception as e:
                            logger.debug('ares device lookup (%s): %s', cli_name, e)
        return None
def _webos_launch_lock(host: str) -> threading.Lock:
    with _webos_launch_locks_guard:
        if host not in _webos_launch_locks:
            _webos_launch_locks[host] = threading.Lock()
        return _webos_launch_locks[host]
def _webos_ipk_version_key(path: Path) -> tuple[int, ...]:
    m = re.search('_(\\d+\\.\\d+\\.\\d+)_', path.name)
    if not m:
        return (0, 0, 0)
    else:
        try:
            return tuple((int(part) for part in m.group(1).split('.')))
        except ValueError:
            return (0, 0, 0)
def resolve_latest_webos_ipk() -> Optional[Path]:
    """dist/ dagi eng yangi com.controlps.lock_*_all.ipk yoki controlps-lock.ipk."""
    base = _resource_dir()
    candidates = []
    seen = set()
    for folder in [base / 'dist', base]:
        if not folder.is_dir():
            continue
        else:
            for pattern in [f'{WEBOS_APP_ID}_*_all.ipk', WEBOS_IPK_NAME]:
                for path in folder.glob(pattern):
                    key = str(path.resolve()).casefold()
                    if key in seen or not path.is_file():
                        continue
                    else:
                        seen.add(key)
                        candidates.append(path)
    if not candidates:
        return
    else:
        return max(candidates, key=lambda p: (_webos_ipk_version_key(p), p.stat().st_mtime))
def _webos_ipk_path() -> Path:
    latest = resolve_latest_webos_ipk()
    if latest:
        return latest
    else:
        return _resource_dir() / WEBOS_IPK_NAME
def webos_setup_status() -> str:
    """webOS uchun nima yetishmayotganini qisqa matn (log/UI uchun)."""
    issues = []
    if not _ares_launch_path():
        issues.append('ares-cli topilmadi (install_tv_tools.bat → 2)')
    ipk = _webos_ipk_path()
    if not ipk.is_file():
        issues.append(f'{WEBOS_IPK_NAME} yo\'q (webos_tv_ornat.bat)')
    if issues:
        return '; '.join(issues)
    else:
        return 'OK'
def _tizen_wgt_path() -> Path:
    base = _resource_dir()
    for p in [base / 'dist' / TIZEN_WGT_NAME, base / TIZEN_WGT_NAME]:
        if p.is_file():
            return p
    return base / TIZEN_WGT_NAME
def webos_install_if_needed(tv_ip: str) -> bool:
    ares_install = _ares_cli_path('ares-install')
    if not ares_install:
        return False
    else:
        ipk = _webos_ipk_path()
        if not ipk.is_file():
            logger.warning('webOS IPK topilmadi: %s', ipk)
            return False
        else:
            device = _ares_device_for_ip(tv_ip) or tv_ip
            try:
                res = _run_cmd([ares_install, '--device', device, str(ipk)], timeout=120)
                out = (res.stdout or '') + (res.stderr or '')
                if res.returncode == 0 or 'Success' in out:
                    print(f'[TVPlatform] webOS IPK o\'rnatildi: {tv_ip}')
                    return True
                else:
                    print(f'[TVPlatform] webOS o\'rnatish: {out[:300]}')
            except Exception as e:
                logger.warning('webOS install: %s', e)
            return False
def webos_close(tv_ip: str) -> bool:
    ares_launch = _ares_launch_path()
    if not ares_launch:
        return False
    else:
        prepare_webos_cli()
        host = (tv_ip or '').split(':', 1)[0].strip()
        device = _ares_device_for_ip(host)
        if not device:
            return False
        else:
            try:
                res = _run_cmd([ares_launch, '--device', device, '-c', WEBOS_APP_ID], timeout=6)
                out = (res.stdout or '') + (res.stderr or '')
                ok = res.returncode == 0 or 'closed' in out.lower() or 'close' in out.lower()
                if ok:
                    print(f'[TVPlatform] webOS close OK: {host} device={device}')
                return ok
            except Exception as e:
                logger.debug('webOS close %s: %s', host, e)
            return False
def webos_hdmi_app_id(hdmi_input: int) -> str:
    port = max(1, min(4, int(hdmi_input or 1)))
    return f'com.webos.app.hdmi{port}'
def webos_launch_app(tv_ip: str, app_id: str, params: Optional[dict[str, Any]]=None, *, label: str='') -> bool:
    ares_launch = _ares_launch_path()
    if not ares_launch:
        msg = 'webOS: ares-launch topilmadi — install_tv_tools.bat (2) yoki tools/ares-cli'
        logger.warning(msg)
        print(f'[TVPlatform] {msg}')
        return False
    else:
        prepare_webos_cli()
        host = (tv_ip or '').split(':', 1)[0].strip()
        if not host or not (app_id or '').strip():
            return False
        else:
            lock = _webos_launch_lock(host)
            if not lock.acquire(timeout=12):
                logger.warning('webOS launch lock timeout: %s', host)
                return False
            else:
                tag = label or app_id
                try:
                    device = _ares_device_for_ip(host)
                    if not device:
                        print(f'[TVPlatform] webOS: qurilma topilmadi ({host}) — webos_tv_ulash.bat')
                        return False
                    args = [ares_launch, '--device', device, app_id.strip()]
                    if params:
                        payload = json.dumps(params, ensure_ascii=False, separators=(',', ':'))
                        args.extend(['-p', payload])
                    res = _run_cmd(args, timeout=25)
                    out = (res.stdout or '') + (res.stderr or '')
                    if res.returncode == 0 or 'launched' in out.lower():
                        msg = f'webOS launch OK ({tag}): {host} device={device}'
                        print(f'[TVPlatform] {msg}')
                        logger.info(msg)
                        return True
                    print(f'[TVPlatform] webOS launch xato ({tag}, device={device}): {out[:300]}')
                    logger.warning('webOS launch failed for %s (%s): %s', host, tag, out[:200])
                    return False
                except Exception as e:
                    logger.warning('webOS launch %s: %s', tag, e)
                    print(f'[TVPlatform] webOS launch exception ({tag}): {e}')
                    return False
                finally:
                    lock.release()
def webos_launch(tv_ip: str, params: Optional[dict[str, Any]]=None) -> bool:
    return webos_launch_app(tv_ip, WEBOS_APP_ID, params, label='lock')
def webos_launch_hdmi(tv_ip: str, hdmi_input: int=1) -> bool:
    """LG tizim HDMI ilovasi — START da PS portiga o\'tish."""
    app_id = webos_hdmi_app_id(hdmi_input)
    return webos_launch_app(tv_ip, app_id, label=app_id)
def webos_wait_until_online(tv_ip: str, timeout_s: float=10.0) -> bool:
    """Wake-on-LAN dan keyin webOS SSH porti ochilishini kutish."""
    host = _webos_host(tv_ip)
    deadline = time.time() + max(1.0, timeout_s)
    while time.time() < deadline:
        if webos_port_open(host, timeout=0.35):
            clear_ares_device_cache(host)
            return True
        time.sleep(0.25)
    return webos_port_open(host, timeout=0.35)
def webos_power_off(tv_ip: str, *, pc_ip: str='', gate_url: str='', hdmi_input: int=1) -> bool:
    """LG webOS STOP: ControlPS Lock ilovasi orqali TV ni standby/off holatiga o\'tkazish."""
    host = _webos_host(tv_ip)
    if not host:
        return False
    else:
        cancel_webos_lock_tasks(host)
        params = build_launch_params(pc_ip, host, gate_url, action='poweroff', hdmi_input=hdmi_input)
        ok = _retry_call(webos_launch, host, params, attempts=2, delays=(0.0, 0.4))
        if ok:
            print(f'[TVPlatform] webOS STOP -> power off: {host}')
            logger.info('webOS STOP power off OK: %s', host)
        else:
            logger.warning('webOS STOP power off xato: %s', host)
        return ok
def webos_set_volume(tv_ip: str, level: int) -> bool:
    """LG webOS ovozini ControlPS Lock ilovasi orqali o\'rnatish (best effort)."""
    host = _webos_host(tv_ip)
    if not host:
        return False
    else:
        level = max(0, min(100, int(level)))
        params = {'tv_ip': host, 'action': 'setvolume', 'volume': str(level)}
        ok = webos_launch(host, params)
        if ok:
            print(f'[TVPlatform] webOS volume -> {level}: {host}')
        return ok
def _webos_host(tv_ip: str) -> str:
    return (tv_ip or '').split(':', 1)[0].strip()
def _webos_should_lock(host: str) -> bool:
    """Seans faol bo\'lsa lock yubormaslik (START/STOP aralashmasin)."""
    if not host:
        return False
    else:
        try:
            import app.tv.tv_handler as tv_handler
            return tv_handler._main_app_lock_gate_active() and tv_handler._should_lock_tv(host)
        except Exception:
            return True
def cancel_webos_lock_tasks(tv_ip: str) -> None:
    """START/seans faol: watchdog va fon lock urinishlarini to\'xtatish."""
    host = _webos_host(tv_ip)
    if not host:
        return
    else:
        try:
            import app.tv.tv_handler as tv_handler
            tv_handler.stop_webos_lock_watchdog(host)
        except Exception as e:
            logger.debug('cancel_webos_lock_tasks: %s', e)
def webos_force_lock(tv_ip: str, params: Optional[dict[str, Any]]=None) -> bool:
    """Home/Exit dan keyin qayta lock — faqat seans bo\'sh bo\'lsa."""
    host = _webos_host(tv_ip)
    if not _webos_should_lock(host):
        return False
    else:
        if webos_launch(tv_ip, params):
            return True
        else:
            if not _webos_should_lock(host):
                return False
            else:
                webos_close(tv_ip)
                time.sleep(0.5)
                if not _webos_should_lock(host):
                    return False
                else:
                    return webos_launch(tv_ip, params)
def tizen_connect(tv_ip: str, port: int=26101) -> bool:
    sdb = _sdb_path()
    if not sdb or not tv_ip:
        return False
    else:
        target = f'{tv_ip}:{port}'
        try:
            _run_cmd([sdb, 'disconnect', target], timeout=5)
            res = _run_cmd([sdb, 'connect', target], timeout=10)
            out = (res.stdout or '') + (res.stderr or '')
            return 'connected' in out.lower() or res.returncode == 0
        except Exception as e:
            logger.debug('Tizen connect: %s', e)
        return False
def tizen_install_if_needed(tv_ip: str) -> bool:
    sdb = _sdb_path()
    wgt = _tizen_wgt_path()
    if not sdb or not wgt.is_file():
        if not wgt.is_file():
            logger.warning('Tizen WGT topilmadi: %s', wgt)
        return False
    else:
        if not tizen_connect(tv_ip):
            return False
        else:
            try:
                res = _run_cmd([sdb, '-s', tv_ip, 'install', str(wgt)], timeout=120)
                out = (res.stdout or '') + (res.stderr or '')
                if res.returncode == 0 or 'successfully' in out.lower():
                    print(f'[TVPlatform] Tizen WGT o\'rnatildi: {tv_ip}')
                    return True
                else:
                    print(f'[TVPlatform] Tizen install: {out[:300]}')
            except Exception as e:
                logger.warning('Tizen install: %s', e)
            return False
def tizen_launch_sdb(tv_ip: str, params: Optional[dict[str, Any]]=None) -> bool:
    sdb = _sdb_path()
    if not sdb:
        return False
    else:
        if not tizen_connect(tv_ip):
            return False
        else:
            payload = ''
            if params:
                payload = ' '.join((f'--es {k} {json.dumps(str(v))}' for k, v in params.items()))
            cmd = f'launch {TIZEN_APP_ID}'
            if payload:
                cmd = f'{cmd} {payload}'
            try:
                res = _run_cmd([sdb, '-s', tv_ip, 'shell', '0', 'was_execute', TIZEN_APP_ID], timeout=10)
                if res.returncode == 0:
                    print(f'[TVPlatform] Tizen launch (was_execute): {tv_ip}')
                    return True
                else:
                    res2 = _run_cmd([sdb, '-s', tv_ip, 'shell', cmd], timeout=10)
                    out = (res2.stdout or '') + (res2.stderr or '')
                    if res2.returncode == 0:
                        print(f'[TVPlatform] Tizen launch OK: {tv_ip}')
                        return True
                    else:
                        print(f'[TVPlatform] Tizen launch: {out[:300]}')
            except Exception as e:
                logger.warning('Tizen launch: %s', e)
            return False
def tizen_launch_ws(tv_ip: str) -> bool:
    """Samsung WebSocket orqali ilovani ishga tushirish."""
    try:
        from samsungtvws import SamsungTVWS
        tv = SamsungTVWS(host=tv_ip, port=8002, name='ControlPS')
        for app_id in (TIZEN_APP_ID, TIZEN_PACKAGE):
            try:
                tv.run_app(app_id)
                print(f'[TVPlatform] Samsung run_app OK: {app_id}')
                return True
            except Exception:
                continue
    except ImportError:
        logger.debug('samsungtvws yo\'q')
    except Exception as e:
        logger.warning('Samsung run_app: %s', e)
    return False
def tizen_launch(tv_ip: str, params: Optional[dict[str, Any]]=None) -> bool:
    if tizen_launch_sdb(tv_ip, params):
        return True
    else:
        return tizen_launch_ws(tv_ip)
def samsung_send_hdmi(tv_ip: str, hdmi_input: int) -> None:
    hdmi_input = max(1, min(4, int(hdmi_input or 1)))
    key = f'KEY_HDMI{hdmi_input}'
    try:
        from samsungtvws import SamsungTVWS
        tv = SamsungTVWS(host=tv_ip, port=8002, name='ControlPS')
        tv.send_key(key, 'Click')
        print(f'[TVPlatform] Samsung HDMI: {key}')
    except Exception as e:
        logger.warning('Samsung HDMI: %s', e)
def samsung_open_lock_browser(tv_ip: str, lock_url: str) -> None:
    try:
        from samsungtvws import SamsungTVWS
        tv = SamsungTVWS(host=tv_ip, port=8002, name='ControlPS')
        tv.open_browser(lock_url)
        print(f'[TVPlatform] Samsung brauzer: {lock_url}')
    except Exception as e:
        logger.warning('Samsung browser: %s', e)
def samsung_send_key(tv_ip: str, key: str) -> None:
    try:
        from samsungtvws import SamsungTVWS
        tv = SamsungTVWS(host=tv_ip, port=8002, name='ControlPS')
        tv.send_key(key, 'Click')
    except Exception as e:
        logger.warning('Samsung key %s: %s', key, e)
def webos_ensure_lock(tv_ip: str, params: Optional[dict[str, Any]]=None) -> bool:
    """Bo\'sh stol: blok ilovasi ishlayotganini tekshirish (flickersiz, 1-2 urinish)."""
    host = _webos_host(tv_ip)
    if not _webos_should_lock(host):
        return False
    else:
        return _retry_call(webos_launch, tv_ip, params, attempts=2, delays=(0.0, 1.0))
def smart_tv_block(tv_ip: str, *, pc_ip: str, gate_url: str, brand: str, lock_browser_url: str='', try_install: bool=False) -> None:
    """STOP: blok ekran — ilovani lock rejimida ishga tushirish."""
    if not tv_ip:
        return
    else:
        params = build_launch_params(pc_ip, tv_ip, gate_url, action='lock')
        launched = False
        if is_webos_brand(brand):
            if try_install:
                webos_install_if_needed(tv_ip)
            launched = _retry_call(webos_launch, tv_ip, params, attempts=3, delays=(0.0, 0.6, 1.5))
            if not launched:
                launched = webos_force_lock(tv_ip, params)
            if launched:
                logger.info('webOS STOP lock OK: %s', tv_ip)
            else:
                logger.warning('webOS STOP lock xato: %s', tv_ip)
        else:
            if is_tizen_brand(brand):
                if try_install:
                    tizen_install_if_needed(tv_ip)
                launched = tizen_launch(tv_ip, params)
                if not launched and lock_browser_url:
                        samsung_open_lock_browser(tv_ip, lock_browser_url)
                        launched = True
        if not launched:
            print(f'[TVPlatform] {brand} TV gate polling kutadi (ilova o\'rnatilgan va PC IP sozlangan bo\'lishi kerak)')
def smart_tv_unblock(tv_ip: str, *, pc_ip: str, gate_url: str, brand: str, hdmi_input: int=1) -> None:
    """START: seans faol — ilovani yopish / HDMI ga qaytish."""
    if not tv_ip:
        return
    else:
        params = build_launch_params(pc_ip, tv_ip, gate_url, action='idle', hdmi_input=hdmi_input)
        if is_webos_brand(brand):
            cancel_webos_lock_tasks(tv_ip)
            hdmi_ok = _retry_call(webos_launch_hdmi, tv_ip, hdmi_input, attempts=2, delays=(0.0, 0.35))
            if hdmi_ok:
                print(f'[TVPlatform] webOS START -> HDMI{hdmi_input}: {tv_ip}')
                logger.info('webOS START -> HDMI%s OK: %s', hdmi_input, tv_ip)
            else:
                if _retry_call(webos_launch, tv_ip, params, attempts=2, delays=(0.0, 0.4)):
                    logger.info('webOS START idle (HDMI zaxira): %s HDMI=%s', tv_ip, hdmi_input)
                else:
                    logger.warning('webOS START xato (HDMI va idle): %s', tv_ip)
        else:
            if is_tizen_brand(brand):
                if not tizen_launch(tv_ip, params):
                    samsung_send_hdmi(tv_ip, hdmi_input)
        print(f'[TVPlatform] {brand} unblock: gate=503, HDMI={hdmi_input}')
def smart_tv_volume(tv_ip: str, brand: str, delta: int) -> None:
    """Ovoz +/- (Tizen WebSocket; webOS hozircha qo\'llab-quvvatlanmaydi)."""
    if not is_tizen_brand(brand) or not tv_ip:
        return None
    else:
        key = 'KEY_VOLUP' if delta > 0 else 'KEY_VOLDOWN'
        for _ in range(abs(int(delta))):
            samsung_send_key(tv_ip, key)
def broadcast_smart_tv_config(stations: list[tuple[str, str, str]], gate_url_builder) -> None:
    """Barcha webOS/Tizen TV larga gate URL ni launch params orqali yuborish."""
    seen = set()
    for entry in stations:
        tv_ip, brand, pc_ip = (entry[0], entry[1], entry[2])
        hdmi_input = int(entry[3]) if len(entry) > 3 else 0
        host = (tv_ip or '').split(':', 1)[0].strip()
        if not host or host in seen:
            continue
        else:
            if not is_smart_tv_brand(brand):
                continue
            else:
                seen.add(host)
                gate_url = gate_url_builder(host)
                params = build_launch_params(pc_ip, host, gate_url, hdmi_input=hdmi_input)
                if is_webos_brand(brand):
                    webos_launch(host, params)
                else:
                    if is_tizen_brand(brand):
                        tizen_launch(host, params)