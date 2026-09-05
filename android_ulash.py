# -*- coding: utf-8 -*-
"""Android TV ni Control PS ga ulash: ADB, lock APK, stol sozlamasi."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CREATE_NO_WINDOW = 0
if sys.platform == 'win32':
    CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

ANDROID_BRANDS = (
    'artel', 'immer', 'tcl', 'xiaomi', 'sony', 'shivaki', 'yasin',
    'premier', 'avalon', 'roison', 'rulls', 'ziffler', 'changhong',
)


def _ask(prompt: str, default: str = '') -> str:
    hint = f' [{default}]' if default else ''
    try:
        val = input(f'{prompt}{hint}: ').strip()
    except EOFError:
        return default
    return val or default


def _run(adb: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding='utf-8',
        errors='replace',
        creationflags=CREATE_NO_WINDOW,
    )


def _out(proc: subprocess.CompletedProcess) -> str:
    return f'{proc.stdout or ""}\n{proc.stderr or ""}'.strip()


def _parse_host_port(raw: str, default_port: int = 5555) -> tuple[str, int]:
    raw = (raw or '').strip()
    host, sep, port_text = raw.rpartition(':')
    if sep and host and port_text.isdigit():
        port = int(port_text)
        if 1 <= port <= 65535:
            return host.strip(), port
    return raw, default_port


def _read_mac(adb: str, device: str) -> str:
    for cmd in (
        ['shell', 'cat', '/sys/class/net/wlan0/address'],
        ['shell', 'cat', '/sys/class/net/eth0/address'],
        ['shell', 'getprop', 'ro.boot.macaddr'],
    ):
        r = _run(adb, '-s', device, *cmd, timeout=8)
        mac = (r.stdout or '').strip().lower()
        if re.fullmatch(r'([0-9a-f]{2}:){5}[0-9a-f]{2}', mac):
            return mac
    return ''


def _wait_authorized(adb: str, device: str, seconds: int = 60) -> bool:
    print('  TV ekranida «USB debugging / ADB ruxsati» chiqsa — OK bosing.')
    deadline = time.time() + seconds
    while time.time() < deadline:
        text = _out(_run(adb, 'devices', timeout=8))
        authorized = False
        unauthorized = False
        for line in text.splitlines():
            if device not in line:
                continue
            parts = line.split()
            if 'unauthorized' in parts:
                unauthorized = True
            elif 'device' in parts:
                authorized = True
        if authorized and not unauthorized:
            return True
        time.sleep(2)
    text = _out(_run(adb, 'devices', timeout=8))
    return device in text and 'unauthorized' not in text


def _connect(adb: str, host: str, port: int) -> bool:
    device = f'{host}:{port}'
    print(f'  ADB ulanmoqda: {device}')
    r = _run(adb, 'connect', device, timeout=12)
    print(' ', _out(r) or '(javob yo\'q)')
    low = _out(r).lower()
    if 'refused' in low or ('failed' in low and 'already' not in low):
        return False
    if 'unauthorized' in low:
        return _wait_authorized(adb, device)
    r2 = _run(adb, 'devices', timeout=8)
    text = _out(r2)
    if device in text and 'unauthorized' in text:
        return _wait_authorized(adb, device)
    return 'connected' in low or 'already connected' in low or (device in text and 'device' in text)


def _pair_if_needed(adb: str) -> None:
    ans = _ask('Wireless debugging pairing kerakmi? (y/n)', 'n').lower()
    if ans not in ('y', 'yes', 'ha', 'h'):
        return
    pair_addr = _ask('TV dagi pairing IP:port (masalan 192.168.1.50:37123)')
    if not pair_addr or ':' not in pair_addr:
        print('  Pairing manzili noto\'g\'ri.')
        return
    code = _ask('6 xonali pairing kod')
    if not code:
        print('  Kod yo\'q.')
        return
    r = _run(adb, 'pair', pair_addr, code, timeout=20)
    print(' ', _out(r) or '(javob yo\'q)')


def _pick_station() -> str:
    import database as db
    ids = [s for s in db.list_station_ids() if s != getattr(db, 'WALKIN_STATION_ID', 'DOKON')]
    if not ids:
        print('  Bazada stol yo\'q. Avval Control PS ni ochib stollar sonini belgilang.')
        return ''
    print('\n  Stollar:')
    for i, sid in enumerate(ids, 1):
        row = db.get_tv_settings(sid)
        name = db.get_station_display_name(sid)
        ip = row.tv_ip or '—'
        print(f'    {i:2}. {name} ({sid})  TV={ip}  {row.brand}')
    raw = _ask('Qaysi stol? (raqam yoki STOL-01, bo\'sh = saqlamaslik)')
    if not raw:
        return ''
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(ids):
            return ids[n - 1]
        print('  Noto\'g\'ri raqam.')
        return ''
    raw_u = raw.upper()
    for sid in ids:
        if sid.upper() == raw_u:
            return sid
    print('  Stol topilmadi.')
    return ''


def main() -> int:
    print('TV da oldin:')
    print('  Sozlamalar → Qurilma haqida → 7 marta «Yadro» / Build')
    print('  Maxfiy sozlamalar → USB debugging  VA  Tarmoq / Wireless debugging')
    print('  TV va kompyuter bir Wi‑Fi da bo\'lsin.\n')

    from app.tv import tv_handler

    adb = tv_handler._get_adb_path()
    if not Path(adb).exists() and adb == 'adb':
        print('ADB topilmadi. Android Studio / SDK platform-tools kerak.')
        print('  %LOCALAPPDATA%\\Android\\Sdk\\platform-tools\\adb.exe')
        return 1
    print(f'ADB: {adb}')
    ver = _run(adb, 'version', timeout=8)
    print(' ', (ver.stdout or '').splitlines()[0] if ver.stdout else _out(ver))

    apk = tv_handler._get_lock_apk_path()
    if not apk.exists():
        print(f'controlps-lock.apk yo\'q: {apk}')
        print('Avval build_apk.bat ni ishga tushiring.')
        return 1
    print(f'APK: {apk}')

    _pair_if_needed(adb)

    ip_raw = _ask('TV IP (masalan 192.168.1.50 yoki 192.168.1.50:5555)')
    if not ip_raw:
        print('IP kiritilmadi.')
        return 1
    host, port = _parse_host_port(ip_raw)
    device = f'{host}:{port}'
    if not _connect(adb, host, port):
        print('Ulanmadi. TV yoqilganligini, ADB ochiqligini va IP ni tekshiring.')
        return 1
    print('  Ulandi.')

    print('\nControlPS Lock o\'rnatilmoqda...')
    ok = tv_handler.provision_android_lock_tv(host, port, force_install=True)
    if not ok:
        print('APK o\'rnatilmadi. TV da overlay ruxsatini qo\'lda bering yoki qayta urinib ko\'ring.')
        return 1
    print('Lock ilova tayyor.')

    mac = _read_mac(adb, device)
    if mac:
        print(f'TV MAC: {mac}')

    sid = _pick_station()
    if not sid:
        print(f'\nControl PS → TV sozlamalari: IP = {device}')
        return 0

    import database as db

    cur = db.get_tv_settings(sid)
    brand = _ask('Brend', cur.brand if (cur.brand or '').lower() in ANDROID_BRANDS else 'artel').lower()
    if brand not in ANDROID_BRANDS:
        print(f'  Noma\'lum brend, artel qilib saqlanadi. Mavjud: {", ".join(ANDROID_BRANDS)}')
        brand = 'artel'
    hdmi_s = _ask('PlayStation qaysi HDMI? (1-4)', str(cur.hdmi_input or 1))
    try:
        hdmi = max(1, min(4, int(hdmi_s)))
    except ValueError:
        hdmi = 1
    ip_save = f'{host}:{port}' if port != 5555 else host
    dup = db.find_station_with_tv_ip(ip_save, exclude_station_id=sid)
    if dup:
        print(f'Bu IP allaqachon {db.get_station_display_name(dup)} ({dup}) da. Saqlanmadi.')
        return 1
    db.set_tv_settings(sid, ip_save, mac or cur.tv_mac, brand, hdmi)
    print(f'\nSaqlandi: {db.get_station_display_name(sid)}  IP={ip_save}  {brand}  HDMI {hdmi}')
    print('Endi ControlPS_v209.exe ni ochib stolni START/STOP bilan tekshiring.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nBekor qilindi.')
        raise SystemExit(1)
    except Exception as e:
        print(f'Xatolik: {e}')
        raise SystemExit(1)
