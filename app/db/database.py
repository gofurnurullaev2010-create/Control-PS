"""\nControl PS — SQLite ma\'lumotlar bazasi: narxlar, TV sozlamalari, seanslar.\n"""
from __future__ import annotations
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional
from app.core.money import as_thousand, round_to_thousand
from app.core.runtime import app_dir
logger = logging.getLogger(__name__)
DB_PATH = app_dir() / 'control_ps.db'
MIN_STATIONS = 1
MAX_STATIONS = 50
WALKIN_STATION_ID = 'DOKON'
def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA synchronous = NORMAL')
    conn.execute('PRAGMA busy_timeout = 30000')
    return conn
def check_database_integrity() -> bool:
    """Baza buzilgan bo\'lsa logga yozadi (yillar davomida ma\'lumotni himoya qilish)."""
    if not DB_PATH.is_file():
        return True
    else:
        conn = _connect()
        try:
            row = conn.execute('PRAGMA integrity_check').fetchone()
            ok = row is not None and str(row[0]).lower() == 'ok'
            if not ok:
                logger.critical('SQLite integrity_check: %s', row[0] if row else '?')
            return ok
        finally:
            conn.close()
def init_db() -> None:
    """Jadvallarni yaratadi va boshlang\'ich qatorlarni qo\'shadi."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute('\n        CREATE TABLE IF NOT EXISTS prices (\n            id INTEGER PRIMARY KEY CHECK (id = 1),\n            hourly_rate REAL NOT NULL DEFAULT 20000.0\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS tv_settings (\n            station_id TEXT PRIMARY KEY,\n            tv_ip TEXT,\n            tv_mac TEXT,\n            brand TEXT NOT NULL DEFAULT \'samsung\',\n            volume INTEGER DEFAULT 50,\n            hdmi_input INTEGER DEFAULT 1\n        )\n        ')
    try:
        cur.execute('SELECT volume FROM tv_settings LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE tv_settings ADD COLUMN volume INTEGER DEFAULT 50')
        print('Database: volume ustuni qo\'shildi')
    try:
        cur.execute('SELECT hdmi_input FROM tv_settings LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE tv_settings ADD COLUMN hdmi_input INTEGER DEFAULT 1')
        print('Database: hdmi_input ustuni qo\'shildi')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS station_prices (\n            station_id TEXT PRIMARY KEY,\n            hourly_rate REAL NOT NULL DEFAULT 20000.0,\n            display_name TEXT,\n            FOREIGN KEY (station_id) REFERENCES tv_settings (station_id)\n        )\n        ')
    try:
        cur.execute('SELECT display_name FROM station_prices LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE station_prices ADD COLUMN display_name TEXT')
        print('Database: station_prices.display_name ustuni qo\'shildi')
    cur.execute('\n        UPDATE station_prices\n        SET display_name = station_id\n        WHERE display_name IS NULL OR TRIM(display_name) = \'\'\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS station_price_slots (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            station_id TEXT NOT NULL,\n            start_minute INTEGER NOT NULL,\n            end_minute INTEGER NOT NULL,\n            hourly_rate REAL NOT NULL,\n            FOREIGN KEY (station_id) REFERENCES station_prices (station_id) ON DELETE CASCADE\n        )\n        ')
    cur.execute('\n        CREATE INDEX IF NOT EXISTS idx_station_price_slots_station\n        ON station_price_slots (station_id, start_minute)\n        ')
    try:
        bad = cur.execute('SELECT id, station_id, hourly_rate FROM station_price_slots WHERE hourly_rate > 100000').fetchall()
        for row in bad:
            rid, sid, rate = (row[0], row[1], float(row[2]))
            fixed = rate / 10.0 if rate / 10.0 <= 100000 else None
            if fixed is None or fixed < 1000:
                fb = cur.execute('SELECT hourly_rate FROM station_prices WHERE station_id = ?', (sid,)).fetchone()
                fixed = float(fb[0]) if fb else 18000.0
            cur.execute('UPDATE station_price_slots SET hourly_rate = ? WHERE id = ?', (fixed, rid))
            print(f'Database: {sid} slot tarifi tuzatildi: {rate:g} → {fixed:g}')
    except Exception:
        pass
    cur.execute('\n        CREATE TABLE IF NOT EXISTS sessions (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            station_id TEXT NOT NULL,\n            start_time TEXT NOT NULL,\n            end_time TEXT,\n            duration_minutes INTEGER,\n            revenue REAL DEFAULT 0,\n            total_seconds INTEGER DEFAULT 0,\n            is_vip INTEGER DEFAULT 0\n        )\n        ')
    try:
        cur.execute('SELECT total_seconds FROM sessions LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE sessions ADD COLUMN total_seconds INTEGER DEFAULT 0')
        print('Database: sessions.total_seconds ustuni qo\'shildi')
    try:
        cur.execute('SELECT is_vip FROM sessions LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE sessions ADD COLUMN is_vip INTEGER DEFAULT 0')
        print('Database: sessions.is_vip ustuni qo\'shildi')
    try:
        cur.execute('SELECT note FROM sessions LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE sessions ADD COLUMN note TEXT NOT NULL DEFAULT \'\'')
        print('Database: sessions.note ustuni qo\'shildi')
    try:
        cur.execute('SELECT billing_rate FROM sessions LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE sessions ADD COLUMN billing_rate REAL NOT NULL DEFAULT 0')
        print('Database: sessions.billing_rate ustuni qo\'shildi')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS drink_prices (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            drink_name TEXT NOT NULL,\n            volume REAL NOT NULL,\n            price REAL NOT NULL,\n            quantity INTEGER NOT NULL DEFAULT 0,\n            UNIQUE(drink_name, volume)\n        )\n        ')
    try:
        cur.execute('SELECT quantity FROM drink_prices LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE drink_prices ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0')
        print('Database: drink_prices.quantity ustuni qo\'shildi')
    try:
        cur.execute('SELECT image FROM drink_prices LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE drink_prices ADD COLUMN image BLOB')
        print('Database: drink_prices.image ustuni qo\'shildi')
    try:
        cur.execute('SELECT cost_price FROM drink_prices LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE drink_prices ADD COLUMN cost_price REAL NOT NULL DEFAULT 0')
        print('Database: drink_prices.cost_price ustuni qo\'shildi')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS drink_orders (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            station_id TEXT NOT NULL,\n            drink_name TEXT NOT NULL,\n            volume REAL NOT NULL,\n            price REAL NOT NULL,\n            order_time TEXT NOT NULL,\n            session_id INTEGER,\n            item_type TEXT NOT NULL DEFAULT \'drink\',\n            FOREIGN KEY (session_id) REFERENCES sessions (id)\n        )\n        ')
    try:
        cur.execute('SELECT item_type FROM drink_orders LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE drink_orders ADD COLUMN item_type TEXT NOT NULL DEFAULT \'drink\'')
        print('Database: drink_orders.item_type ustuni qo\'shildi')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS market_products (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            name TEXT NOT NULL,\n            price REAL NOT NULL,\n            category TEXT,\n            description TEXT,\n            grams REAL NOT NULL DEFAULT 0,\n            quantity INTEGER NOT NULL DEFAULT 0,\n            image BLOB\n        )\n        ')
    for col, ddl in [('grams', 'ALTER TABLE market_products ADD COLUMN grams REAL NOT NULL DEFAULT 0'), ('quantity', 'ALTER TABLE market_products ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0'), ('image', 'ALTER TABLE market_products ADD COLUMN image BLOB'), ('cost_price', 'ALTER TABLE market_products ADD COLUMN cost_price REAL NOT NULL DEFAULT 0')]:
        try:
            cur.execute(f'SELECT {col} FROM market_products LIMIT 1')
        except sqlite3.OperationalError:
            cur.execute(ddl)
            print(f'Database: market_products.{col} ustuni qo\'shildi')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS joystick_tests (\n            station_id TEXT NOT NULL,\n            test_date TEXT NOT NULL,\n            attempts INTEGER NOT NULL DEFAULT 0,\n            PRIMARY KEY (station_id, test_date)\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS app_settings (\n            key TEXT PRIMARY KEY,\n            value TEXT NOT NULL\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS operator_reports (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            operator_index INTEGER NOT NULL,\n            business_day TEXT NOT NULL,\n            saved_time TEXT NOT NULL,\n            period_start TEXT NOT NULL,\n            period_end TEXT NOT NULL,\n            total_revenue REAL DEFAULT 0,\n            session_revenue REAL DEFAULT 0,\n            drink_revenue REAL DEFAULT 0,\n            market_revenue REAL DEFAULT 0,\n            joystick_revenue REAL DEFAULT 0,\n            details_json TEXT\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS cash_closes (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            business_day TEXT NOT NULL,\n            operator_index INTEGER NOT NULL,\n            operator_name TEXT NOT NULL DEFAULT \'\',\n            saved_time TEXT NOT NULL,\n            total_income REAL NOT NULL DEFAULT 0,\n            expense_total REAL NOT NULL DEFAULT 0,\n            debt_total REAL NOT NULL DEFAULT 0,\n            debt_paid_total REAL NOT NULL DEFAULT 0,\n            closing_amount REAL NOT NULL DEFAULT 0,\n            expected_amount REAL NOT NULL DEFAULT 0,\n            cash_diff REAL NOT NULL DEFAULT 0,\n            period_start TEXT,\n            period_end TEXT\n        )\n        ')
    try:
        cur.execute('SELECT click_total FROM cash_closes LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE cash_closes ADD COLUMN click_total REAL NOT NULL DEFAULT 0')
    cur.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (\'safe_balance\', \'0\')')
    cur.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (\'cash_period_start\', \'\')')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS debtors (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            client_name TEXT NOT NULL,\n            phone TEXT,\n            amount REAL NOT NULL DEFAULT 0,\n            debt_time TEXT NOT NULL,\n            note TEXT,\n            paid INTEGER NOT NULL DEFAULT 0,\n            paid_time TEXT\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS debt_payment_events (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            debtor_id INTEGER,\n            client_name TEXT NOT NULL DEFAULT \'\',\n            phone TEXT NOT NULL DEFAULT \'\',\n            amount REAL NOT NULL DEFAULT 0,\n            paid_time TEXT NOT NULL,\n            note TEXT NOT NULL DEFAULT \'\'\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS bookings (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            client_name TEXT NOT NULL,\n            phone TEXT,\n            station_id TEXT,\n            booking_time TEXT NOT NULL,\n            note TEXT,\n            status TEXT NOT NULL DEFAULT \'active\',\n            created_time TEXT NOT NULL\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS expenses (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            expense_type TEXT NOT NULL,\n            amount REAL NOT NULL DEFAULT 0,\n            wallet TEXT NOT NULL DEFAULT \'cash\',\n            note TEXT,\n            created_time TEXT NOT NULL\n        )\n        ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS click_entries (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            amount REAL NOT NULL DEFAULT 0,\n            created_time TEXT NOT NULL\n        )\n        ')
    cur.execute('\n        INSERT OR IGNORE INTO app_settings (key, value) VALUES (\'day_start_time\', \'00:00\')\n        ')
    cur.execute('\n        INSERT OR IGNORE INTO app_settings (key, value) VALUES (\'joystick_price\', \'3000\')\n        ')
    cur.execute('SELECT COUNT(*) FROM prices')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO prices (id, hourly_rate) VALUES (1, ?)', (20000.0,))
    for i in range(1, 9):
        sid = f'STOL-{i:02d}'
        cur.execute('SELECT 1 FROM tv_settings WHERE station_id = ?', (sid,))
        if cur.fetchone() is None:
            cur.execute('INSERT INTO tv_settings (station_id, tv_ip, tv_mac, brand, hdmi_input) VALUES (?, \'\', \'\', \'samsung\', 1)', (sid,))
            cur.execute('\n                INSERT OR IGNORE INTO station_prices (station_id, hourly_rate, display_name)\n                VALUES (?, ?, ?)\n                ', (sid, 20000.0, sid))
    default_drinks = [('Kola', 0.5, 5000), ('Pepsi', 0.5, 5000), ('Fanta', 0.5, 5000), ('Sprite', 0.5, 5000), ('Flash', 0.5, 8000), ('Gorilla', 0.5, 12000)]
    for drink_name, volume, price in default_drinks:
        cur.execute('SELECT 1 FROM drink_prices WHERE drink_name = ? AND volume = ?', (drink_name, volume))
        if cur.fetchone() is None:
            cur.execute('INSERT INTO drink_prices (drink_name, volume, price) VALUES (?, ?, ?)', (drink_name, volume, price))
    conn.commit()
    conn.close()
    try:
        if not check_database_integrity():
            logger.warning('Baza tekshiruvi muvaffaqiyatsiz. control_ps_backup_*.db dan tiklash mumkin.')
        backup_database_if_needed()
    except Exception as e:
        logger.warning('Baza zaxirasi: %s', e)
def backup_database_if_needed(max_keep: int=30) -> None:
    """Kuniga bir marta control_ps.db nusxasi (control_ps_backup_YYYY-MM-DD.db)."""
    import shutil
    if not DB_PATH.is_file():
        return
    else:
        stamp = date.today().isoformat()
        dest = DB_PATH.parent / f'control_ps_backup_{stamp}.db'
        if dest.is_file():
            return
        else:
            shutil.copy2(DB_PATH, dest)
            backups = sorted(DB_PATH.parent.glob('control_ps_backup_*.db'), reverse=True)
            for old in backups[max_keep:]:
                try:
                    old.unlink()
                except OSError:
                    pass
def get_hourly_rate() -> float:
    conn = _connect()
    row = conn.execute('SELECT hourly_rate FROM prices WHERE id = 1').fetchone()
    conn.close()
    return float(row['hourly_rate']) if row else 20000.0
def set_hourly_rate(rate: float) -> None:
    conn = _connect()
    conn.execute('UPDATE prices SET hourly_rate = ? WHERE id = 1', (rate,))
    conn.commit()
    conn.close()
def get_joystick_price() -> float:
    """Qo\'shimcha (bepul 2 tadan ortiq) har bir jostik narxi."""
    conn = _connect()
    row = conn.execute('SELECT value FROM app_settings WHERE key = \'joystick_price\'').fetchone()
    conn.close()
    if row:
        try:
            return float(row['value'])
        except (ValueError, TypeError):
            pass
    return 3000.0
def set_joystick_price(price: float) -> None:
    conn = _connect()
    conn.execute('\n        INSERT INTO app_settings (key, value) VALUES (\'joystick_price\', ?)\n        ON CONFLICT(key) DO UPDATE SET value = excluded.value\n        ', (str(int(max(0, price))),))
    conn.commit()
    conn.close()
def add_joystick_charge(station_id: str, price: float, session_id: Optional[int]=None) -> None:
    """Qo\'shimcha jostikni yozadi (soatbay narx).\n\n    ``volume`` maydonida soatlik narx saqlanadi; yakuniy summa seans davomida\n    va STOP da ``order_time`` dan boshlab vaqt bo\'yicha hisoblanadi.\n    Masalan: 3000 so\'m/soat, 30 daqiqa → 1500 so\'m.\n    """
    conn = _connect()
    now = _session_wall_now_iso()
    hourly = float(max(0.0, price))
    conn.execute('\n        INSERT INTO drink_orders (station_id, drink_name, volume, price, order_time, session_id, item_type)\n        VALUES (?, \'Jostik\', ?, 0, ?, ?, \'joystick\')\n        ', (station_id, hourly, now, session_id))
    conn.commit()
    conn.close()
def count_joystick_charges(session_id: Optional[int]) -> int:
    """Seansda nechta qo\'shimcha (pullik) jostik olinganini qaytaradi."""
    if not session_id:
        return 0
    else:
        conn = _connect()
        row = conn.execute('SELECT COUNT(*) FROM drink_orders WHERE session_id = ? AND item_type = \'joystick\'', (session_id,)).fetchone()
        conn.close()
        return int(row[0] or 0)
def _parse_order_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return
    else:
        if isinstance(value, datetime):
            return value
        else:
            text = str(value).strip()
            if not text:
                return
            else:
                try:
                    return datetime.fromisoformat(text)
                except ValueError:
                    return None
def joystick_accrued_amount(hourly_rate: float, order_time: Any, until: Optional[datetime]=None) -> float:
    """Jostik soatlik narxidan order_time → until oralig\'idagi summa (minglik)."""
    start = _parse_order_dt(order_time)
    if start is None:
        return 0.0
    else:
        if until is None:
            try:
                from app.core.network_time import trusted_now_naive
                until = trusted_now_naive()
            except Exception:
                until = datetime.now()
        hours = max(0.0, (until - start).total_seconds() / 3600.0)
        return round_to_thousand(float(hourly_rate or 0) * hours)
def _joystick_line_amount(*, volume: float, price: float, order_time: Any, session_active: bool, until: Optional[datetime]=None) -> float:
    """Jostik qatori summasi: yangi format (volume=soatlik) yoki eski flat price.\n\n    STOP dan keyin finalize price > 0 yozadi — qayta hisoblamaslik kerak.\n    """
    rate = float(volume or 0)
    stored = float(price or 0)
    if stored > 0:
        return stored
    else:
        if rate > 0:
            return joystick_accrued_amount(rate, order_time, until)
        else:
            return 0.0
def finalize_joystick_charges(session_id: Optional[int], end_time: Optional[datetime]=None) -> float:
    """Seansdagi jostiklarni vaqt bo\'yicha yakuniy narxga yozadi. Jami qaytaradi."""
    if not session_id:
        return 0.0
    else:
        if end_time is None:
            try:
                from app.core.network_time import trusted_now_naive
                end_time = trusted_now_naive()
            except Exception:
                end_time = datetime.now()
        end = end_time
        conn = _connect()
        rows = conn.execute('\n        SELECT id, volume, price, order_time\n        FROM drink_orders\n        WHERE session_id = ? AND item_type = \'joystick\'\n        ', (int(session_id),)).fetchall()
        total = 0.0
        for r in rows:
            rate = float(r['volume'] or 0)
            if rate > 0:
                amount = round_to_thousand(joystick_accrued_amount(rate, r['order_time'], end))
                conn.execute('UPDATE drink_orders SET price = ? WHERE id = ?', (amount, int(r['id'])))
                total += amount
            else:
                total += round_to_thousand(float(r['price'] or 0))
        conn.commit()
        conn.close()
        return round_to_thousand(total)
DEFAULT_DAY_START_TIME = '00:00'
def get_business_day_start() -> tuple[int, int]:
    """Kun boshlanish vaqti (soat, daqiqa). Masalan 06:00 — kechasi 05:59 gacha oldingi kun."""
    conn = _connect()
    row = conn.execute('SELECT value FROM app_settings WHERE key = \'day_start_time\'').fetchone()
    conn.close()
    if row:
        parts = str(row['value'] or '').strip().split(':')
        if len(parts) == 2:
            try:
                return (max(0, min(23, int(parts[0]))), max(0, min(59, int(parts[1]))))
            except ValueError:
                pass
    return (0, 0)
def get_business_day_start_str() -> str:
    h, m = get_business_day_start()
    return f'{h:02d}:{m:02d}'
def set_business_day_start(hour: int, minute: int) -> None:
    h = max(0, min(23, int(hour)))
    m = max(0, min(59, int(minute)))
    value = f'{h:02d}:{m:02d}'
    conn = _connect()
    conn.execute('\n        INSERT INTO app_settings (key, value) VALUES (\'day_start_time\', ?)\n        ON CONFLICT(key) DO UPDATE SET value = excluded.value\n        ', (value,))
    conn.commit()
    conn.close()
def business_date_for_dt(dt: datetime) -> date:
    """Berilgan vaqt qaysi biznes kuniga tegishli ekanini qaytaradi."""
    h, m = get_business_day_start()
    day_start = dt.replace(hour=h, minute=m, second=0, microsecond=0)
    if dt < day_start:
        return dt.date() - timedelta(days=1)
    else:
        return dt.date()
def current_business_date() -> date:
    """Hozirgi biznes kuni (kassa kunini hisoblash uchun)."""
    try:
        from app.core.network_time import trusted_now_naive
        return business_date_for_dt(trusted_now_naive())
    except Exception:
        return business_date_for_dt(datetime.now())
def business_day_bounds(day: str | date) -> tuple[str, str]:
    """Biznes kuni oralig\'i: [boshlanish, keyingi kun boshlanishi) ISO formatda."""
    d = date.fromisoformat(day) if isinstance(day, str) else day
    h, m = get_business_day_start()
    start = datetime(d.year, d.month, d.day, h, m, 0)
    end = start + timedelta(days=1)
    return (start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds'))
@dataclass
class TVSettingRow:
    station_id: str
    tv_ip: str
    tv_mac: str
    brand: str
    volume: int
    hdmi_input: int
def get_tv_settings(station_id: str) -> TVSettingRow:
    conn = _connect()
    row = conn.execute('SELECT station_id, tv_ip, tv_mac, brand, volume, hdmi_input FROM tv_settings WHERE station_id = ?', (station_id,)).fetchone()
    conn.close()
    if not row:
        return TVSettingRow(station_id, '', '', 'samsung', 50, 1)
    else:
        return TVSettingRow(
            row['station_id'],
            row['tv_ip'] or '',
            (row['tv_mac'] or '').lower(),
            (row['brand'] or 'samsung'),
            (int(row['volume']) if row['volume'] is not None else 50),
            max(1, min(4, int(row['hdmi_input']) if row['hdmi_input'] is not None else 1)),
        )
def normalize_tv_ip_host(tv_ip: str) -> str:
    """TV IP maydonidan faqat host (192.168.1.10:5555 -> 192.168.1.10)."""
    raw = (tv_ip or '').strip()
    if not raw:
        return ''
    else:
        host, sep, port_text = raw.rpartition(':')
        if sep and host and port_text.isdigit():
            return host.strip()
        else:
            return raw
def find_station_with_tv_ip(tv_ip: str, *, exclude_station_id: str='') -> Optional[str]:
    """Boshqa stolda shu TV IP allaqachon ishlatilgan bo\'lsa station_id qaytaradi."""
    host = normalize_tv_ip_host(tv_ip)
    if not host:
        return
    else:
        exclude = (exclude_station_id or '').strip()
        for sid in list_station_ids():
            if sid == exclude:
                continue
            else:
                row = get_tv_settings(sid)
                if normalize_tv_ip_host(row.tv_ip) == host:
                    return sid
        return None
def set_tv_settings(station_id: str, tv_ip: str, tv_mac: str, brand: str, hdmi_input: int=1) -> None:
    conn = _connect()
    conn.execute('\n        INSERT INTO tv_settings (station_id, tv_ip, tv_mac, brand, hdmi_input)\n        VALUES (?, ?, ?, ?, ?)\n        ON CONFLICT(station_id) DO UPDATE SET\n            tv_ip = excluded.tv_ip,\n            tv_mac = excluded.tv_mac,\n            brand = excluded.brand,\n            hdmi_input = excluded.hdmi_input\n        ', (station_id, tv_ip.strip(), tv_mac.strip(), brand.lower(), max(1, min(4, int(hdmi_input)))))
    conn.commit()
    conn.close()
def set_tv_volume(station_id: str, volume: int) -> None:
    """Televizor ovozini saqlash (0-100)."""
    conn = _connect()
    conn.execute('\n        INSERT INTO tv_settings (station_id, tv_ip, tv_mac, brand, volume)\n        VALUES (?, \'\', \'\', \'samsung\', ?)\n        ON CONFLICT(station_id) DO UPDATE SET\n            volume = excluded.volume\n        ', (station_id, max(0, min(100, volume))))
    conn.commit()
    conn.close()
def joystick_attempts_used(station_id: str, day: Optional[str]=None) -> int:
    """Bugun JOSTIK test tugmasi nechta ishlatilganini qaytaradi."""
    day = day or current_business_date().isoformat()
    conn = _connect()
    row = conn.execute('SELECT attempts FROM joystick_tests WHERE station_id = ? AND test_date = ?', (station_id, day)).fetchone()
    conn.close()
    return int(row['attempts']) if row else 0
def joystick_attempts_remaining(station_id: str, limit: int=3, day: Optional[str]=None) -> int:
    return max(0, int(limit) - joystick_attempts_used(station_id, day))
def record_joystick_attempt(station_id: str, limit: int=3, day: Optional[str]=None) -> int:
    """JOSTIK test urinishini yozadi; qaytadigan qiymat - qolgan urinishlar."""
    day = day or current_business_date().isoformat()
    conn = _connect()
    cur = conn.execute('SELECT attempts FROM joystick_tests WHERE station_id = ? AND test_date = ?', (station_id, day))
    row = cur.fetchone()
    used = int(row['attempts']) if row else 0
    if used >= limit:
        conn.close()
        return 0
    else:
        used += 1
        conn.execute('\n        INSERT INTO joystick_tests (station_id, test_date, attempts)\n        VALUES (?, ?, ?)\n        ON CONFLICT(station_id, test_date) DO UPDATE SET\n            attempts = excluded.attempts\n        ', (station_id, day, used))
        conn.commit()
        conn.close()
        return max(0, int(limit) - used)
def list_station_ids() -> List[str]:
    conn = _connect()
    rows = conn.execute('SELECT station_id FROM tv_settings ORDER BY station_id').fetchall()
    conn.close()
    return [r['station_id'] for r in rows]
def update_station_count(new_count: int) -> None:
    """Stollar sonini o\'zgartirish"""
    new_count = max(MIN_STATIONS, min(MAX_STATIONS, int(new_count)))
    conn = _connect()
    cur = conn.cursor()
    cur.execute('SELECT station_id FROM tv_settings ORDER BY station_id')
    current_stations = [row[0] for row in cur.fetchall()]
    new_stations = [f'STOL-{i:02d}' for i in range(1, new_count + 1)]
    stations_to_add = [s for s in new_stations if s not in current_stations]
    stations_to_remove = [s for s in current_stations if s not in new_stations]
    for station_id in stations_to_add:
        cur.execute('INSERT INTO tv_settings (station_id, tv_ip, tv_mac, brand) VALUES (?, \'\', \'\', \'samsung\')', (station_id,))
        cur.execute('\n            INSERT OR IGNORE INTO station_prices (station_id, hourly_rate, display_name)\n            VALUES (?, ?, ?)\n            ', (station_id, 20000.0, station_id))
    for station_id in stations_to_remove:
        cur.execute('DELETE FROM station_price_slots WHERE station_id = ?', (station_id,))
        cur.execute('DELETE FROM station_prices WHERE station_id = ?', (station_id,))
        cur.execute('DELETE FROM tv_settings WHERE station_id = ?', (station_id,))
    conn.commit()
    conn.close()
def get_station_count() -> int:
    """Stollar sonini olish"""
    conn = _connect()
    count = conn.execute('SELECT COUNT(*) FROM tv_settings').fetchone()[0]
    conn.close()
    return count
def get_station_price(station_id: str) -> float:
    """Stol narxini olish"""
    conn = _connect()
    row = conn.execute('SELECT hourly_rate FROM station_prices WHERE station_id = ?', (station_id,)).fetchone()
    conn.close()
    return float(row['hourly_rate']) if row else 20000.0
def _minute_to_hhmm(minute: int) -> str:
    minute = int(minute) % 1440
    return f'{minute // 60:02d}:{minute % 60:02d}'
def _hhmm_to_minute(value: str) -> int:
    text = str(value or '').strip()
    if not text:
        return 0
    else:
        parts = text.split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return max(0, min(23, hour)) * 60 + max(0, min(59, minute))
def get_station_price_slots(station_id: str) -> list[dict[str, Any]]:
    """Stol uchun vaqt oralig\'i tariflarini qaytaradi."""
    conn = _connect()
    rows = conn.execute('\n        SELECT start_minute, end_minute, hourly_rate\n        FROM station_price_slots\n        WHERE station_id = ?\n        ORDER BY start_minute, id\n        ', (station_id,)).fetchall()
    conn.close()
    return [{'start': _minute_to_hhmm(row['start_minute']), 'end': _minute_to_hhmm(row['end_minute']), 'start_minute': int(row['start_minute']), 'end_minute': int(row['end_minute']), 'hourly_rate': float(row['hourly_rate'])} for row in rows]
_MAX_HOURLY_RATE = 100000.0
def _sanitize_hourly_rate(rate: float, fallback: float=0.0) -> float:
    """Manfiy yoki g\'ayritabiiy tarifni tuzatadi (masalan ortiqcha 0)."""
    try:
        r = float(rate or 0)
    except (TypeError, ValueError):
        r = 0.0
    if r < 0:
        r = 0.0
    fb = max(0.0, float(fallback or 0))
    if r > _MAX_HOURLY_RATE:
        if r / 10.0 <= _MAX_HOURLY_RATE and r / 10.0 >= 1000:
            r = r / 10.0
        else:
            r = fb if fb > 0 else 0.0
    return r
def set_station_price_slots(station_id: str, slots: list[dict[str, Any]]) -> None:
    """Stol uchun vaqt oralig\'i tariflarini qayta saqlaydi."""
    fallback = float(get_station_price(station_id) or 0)
    normalized = []
    for slot in slots:
        if not slot:
            continue
        else:
            start_raw = slot.get('start_minute', slot.get('start', '00:00'))
            end_raw = slot.get('end_minute', slot.get('end', '00:00'))
            start_minute = int(start_raw) if isinstance(start_raw, int) else _hhmm_to_minute(str(start_raw))
            end_minute = int(end_raw) if isinstance(end_raw, int) else _hhmm_to_minute(str(end_raw))
            hourly_rate = _sanitize_hourly_rate(float(slot.get('hourly_rate', 0) or 0), fallback)
            normalized.append((start_minute % 1440, end_minute % 1440, hourly_rate))
    conn = _connect()
    cur = conn.cursor()
    cur.execute('DELETE FROM station_price_slots WHERE station_id = ?', (station_id,))
    for start_minute, end_minute, hourly_rate in normalized:
        cur.execute('\n            INSERT INTO station_price_slots (station_id, start_minute, end_minute, hourly_rate)\n            VALUES (?, ?, ?, ?)\n            ', (station_id, start_minute, end_minute, hourly_rate))
    conn.commit()
    conn.close()
def _slot_matches_minute(slot: dict[str, Any], minute: int) -> bool:
    start_minute = int(slot['start_minute'])
    end_minute = int(slot['end_minute'])
    if start_minute == end_minute:
        return True
    else:
        if start_minute < end_minute:
            return start_minute <= minute < end_minute
        else:
            return minute >= start_minute or minute < end_minute
def get_station_rate_at(station_id: str, at_time: Optional[datetime]=None) -> float:
    """Berilgan vaqtdagi stol tarifini qaytaradi."""
    at_time = at_time or datetime.now()
    minute = at_time.hour * 60 + at_time.minute
    fallback = float(get_station_price(station_id) or 0)
    slots = get_station_price_slots(station_id)
    for slot in slots:
        if _slot_matches_minute(slot, minute):
            return _sanitize_hourly_rate(float(slot['hourly_rate']), fallback)
    return max(0.0, fallback)
def calculate_station_time_revenue(station_id: str, start_time: Optional[datetime], elapsed_seconds: int, *, lock_rate_at_start: bool=False, billing_rate: Optional[float]=None) -> float:
    """PS summasi: qulflangan (yoki start) tarif × soniyalar/3600.\n\n    Eski chaqiruvlar uchun mos: elapsed_seconds beriladi.\n    lock_rate_at_start / billing_rate — tarifni qulflash.\n    """
    from app.core.ps_billing import resolve_billing_rate, sanitize_hourly_rate, time_amount
    seconds = max(0, int(elapsed_seconds or 0))
    if seconds <= 0:
        return 0.0
    else:
        if start_time is None:
            try:
                from app.core.network_time import trusted_now_naive
                start_time = trusted_now_naive() - timedelta(seconds=seconds)
            except Exception:
                start_time = datetime.now() - timedelta(seconds=seconds)
        if billing_rate is not None and float(billing_rate or 0) > 0:
            rate = sanitize_hourly_rate(billing_rate, 0.0)
        else:
            if lock_rate_at_start:
                rate = resolve_billing_rate(station_id, start_time, None)
            else:
                fallback_rate = sanitize_hourly_rate(get_station_price(station_id) or 0, 0.0)
                slots_raw = get_station_price_slots(station_id)
                slots = []
                for s in slots_raw:
                    sc = dict(s)
                    sc['hourly_rate'] = sanitize_hourly_rate(float(s.get('hourly_rate') or 0), fallback_rate)
                    slots.append(sc)
                if not slots:
                    return time_amount(fallback_rate, seconds)
                else:
                    rates = {float(s.get('hourly_rate') or 0) for s in slots}
                    if len(rates) == 1:
                        only = next(iter(rates))
                        rate = only if only > 0 else fallback_rate
                        return time_amount(rate, seconds)
                    else:
                        end_time = start_time + timedelta(seconds=seconds)
                        current = start_time
                        total = 0.0
                        guard = 0
                        while current < end_time and guard < 200000:
                                guard += 1
                                next_minute = (current + timedelta(minutes=1)).replace(second=0, microsecond=0)
                                if next_minute <= current:
                                    next_minute = current + timedelta(minutes=1)
                                segment_end = min(end_time, next_minute)
                                minute = current.hour * 60 + current.minute
                                rate = fallback_rate
                                for slot in slots:
                                    if _slot_matches_minute(slot, minute):
                                        rate = float(slot['hourly_rate'])
                                        break
                                total += rate * ((segment_end - current).total_seconds() / 3600.0)
                                current = segment_end
                        return float(total)
        return time_amount(rate, seconds)
def set_station_price(station_id: str, rate: float) -> None:
    """Stol narxini o\'rnatish"""
    conn = _connect()
    conn.execute('\n        INSERT INTO station_prices (station_id, hourly_rate, display_name)\n        VALUES (?, ?, ?)\n        ON CONFLICT(station_id) DO UPDATE SET\n            hourly_rate = excluded.hourly_rate\n        ', (station_id, rate, station_id))
    conn.commit()
    conn.close()
def get_station_display_name(station_id: str) -> str:
    """Stolning ekranda ko\'rinadigan nomi (masalan KABINA)."""
    conn = _connect()
    row = conn.execute('SELECT display_name FROM station_prices WHERE station_id = ?', (station_id,)).fetchone()
    conn.close()
    if row and row['display_name'] and str(row['display_name']).strip():
        return str(row['display_name']).strip()
    else:
        return station_id
def set_station_display_name(station_id: str, display_name: str) -> None:
    """Stol ko\'rinadigan nomini saqlash."""
    name = (display_name or '').strip() or station_id
    conn = _connect()
    conn.execute('\n        INSERT INTO station_prices (station_id, hourly_rate, display_name)\n        VALUES (?, ?, ?)\n        ON CONFLICT(station_id) DO UPDATE SET\n            display_name = excluded.display_name\n        ', (station_id, get_station_price(station_id), name))
    conn.commit()
    conn.close()
def set_station_price_and_name(station_id: str, rate: float, display_name: str) -> None:
    """Stol narxini va ko\'rinadigan nomini birga saqlash."""
    name = (display_name or '').strip() or station_id
    conn = _connect()
    conn.execute('\n        INSERT INTO station_prices (station_id, hourly_rate, display_name)\n        VALUES (?, ?, ?)\n        ON CONFLICT(station_id) DO UPDATE SET\n            hourly_rate = excluded.hourly_rate,\n            display_name = excluded.display_name\n        ', (station_id, rate, name))
    conn.commit()
    conn.close()
def get_all_station_prices() -> dict:
    """Barcha stollar narxini olish"""
    conn = _connect()
    rows = conn.execute('SELECT station_id, hourly_rate FROM station_prices ORDER BY station_id').fetchall()
    conn.close()
    return {row['station_id']: row['hourly_rate'] for row in rows}
def _session_wall_now_iso() -> str:
    """Seans start/end — onlayn soat (uzilsa oxirgi sinxrondan davom)."""
    try:
        from app.core.network_time import trusted_now_naive
        return trusted_now_naive().isoformat(timespec='seconds')
    except Exception:
        return datetime.now().isoformat(timespec='seconds')
def start_session_row(station_id: str, total_seconds: int=0, is_vip: bool=False) -> int:
    """Yangi seans boshlanadi; qaytarilgan id keyin tugatish uchun.\n\n    billing_rate — start paytidagi tarif (keyin o\'zgarmaydi → PS xato chiqmasin).\n    """
    from app.core.ps_billing import resolve_billing_rate
    conn = _connect()
    now = _session_wall_now_iso()
    try:
        start_dt = datetime.fromisoformat(now)
    except Exception:
        start_dt = datetime.now()
    rate = resolve_billing_rate(station_id, start_dt, None)
    try:
        cur = conn.execute('\n            INSERT INTO sessions (station_id, start_time, total_seconds, is_vip, billing_rate)\n            VALUES (?, ?, ?, ?, ?)\n            ', (station_id, now, max(0, int(total_seconds)), 1 if is_vip else 0, float(rate)))
    except sqlite3.OperationalError:
        cur = conn.execute('INSERT INTO sessions (station_id, start_time, total_seconds, is_vip) VALUES (?, ?, ?, ?)', (station_id, now, max(0, int(total_seconds)), 1 if is_vip else 0))
    sid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return sid
def end_session_row(session_db_id: int, duration_minutes: int, revenue: float) -> None:
    conn = _connect()
    now = _session_wall_now_iso()
    conn.execute('\n        UPDATE sessions\n        SET end_time = ?, duration_minutes = ?, revenue = ?\n        WHERE id = ?\n        ', (now, duration_minutes, revenue, session_db_id))
    conn.commit()
    conn.close()
def update_session_total_seconds(session_db_id: int, total_seconds: int) -> None:
    """Vaqt qo\'shilganda active seans total vaqtini bazaga saqlash."""
    conn = _connect()
    conn.execute('UPDATE sessions SET total_seconds = ? WHERE id = ? AND end_time IS NULL', (max(0, int(total_seconds)), session_db_id))
    conn.commit()
    conn.close()
def transfer_active_session(session_db_id: int, new_station_id: str) -> bool:
    """Faol seansni boshqa stolga ko\'chirish (VIP va ichimliklar bilan)."""
    conn = _connect()
    row = conn.execute('SELECT id FROM sessions WHERE id = ? AND end_time IS NULL', (int(session_db_id),)).fetchone()
    if not row:
        conn.close()
        return False
    else:
        conn.execute('UPDATE sessions SET station_id = ? WHERE id = ? AND end_time IS NULL', (new_station_id, int(session_db_id)))
        conn.execute('UPDATE drink_orders SET station_id = ? WHERE session_id = ?', (new_station_id, int(session_db_id)))
        conn.commit()
        conn.close()
        return True
def active_session_for_station(station_id: str) -> Optional[dict[str, Any]]:
    """Stol uchun tugallanmagan oxirgi seansni qaytaradi."""
    conn = _connect()
    try:
        row = conn.execute('\n            SELECT id, station_id, start_time, total_seconds, is_vip,\n                   COALESCE(billing_rate, 0) AS billing_rate\n            FROM sessions\n            WHERE station_id = ? AND end_time IS NULL\n            ORDER BY start_time DESC\n            LIMIT 1\n            ', (station_id,)).fetchone()
    except sqlite3.OperationalError:
        row = conn.execute('\n            SELECT id, station_id, start_time, total_seconds, is_vip\n            FROM sessions\n            WHERE station_id = ? AND end_time IS NULL\n            ORDER BY start_time DESC\n            LIMIT 1\n            ', (station_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
def today_revenue_total() -> float:
    """Joriy kassa davri tushumi (oxirgi kassa jabıwdan keyin). Active seanslar qo\'shilmaydi."""
    return float(cash_period_revenue().get('total') or 0)
def revenue_total_for_day(day: str) -> float:
    """Kun bo\'yicha yakunlangan jami tushum (YYYY-MM-DD). Active seanslar qo\'shilmaydi."""
    return revenue_split_for_day(day)['total']
def revenue_total_all_time() -> float:
    """Dastur ochilgandan beri barcha yakunlangan tushum (active seanslarsiz)."""
    conn = _connect()
    ended = conn.execute('\n        SELECT\n            COALESCE(s.revenue, 0) AS revenue,\n            COALESCE((\n                SELECT SUM(d.price) FROM drink_orders d WHERE d.session_id = s.id\n                  AND lower(COALESCE(d.item_type, \'drink\')) != \'buyurtma\'\n            ), 0) AS drink_rev\n        FROM sessions s\n        WHERE s.end_time IS NOT NULL\n        ').fetchall()
    session_time = 0.0
    for r in ended:
        session_time += max(0.0, float(r['revenue'] or 0) - float(r['drink_rev'] or 0))
    ended_drinks = float(conn.execute('\n            SELECT COALESCE(SUM(d.price), 0)\n            FROM drink_orders d\n            JOIN sessions s ON d.session_id = s.id\n            WHERE s.end_time IS NOT NULL\n              AND lower(COALESCE(d.item_type, \'drink\')) != \'buyurtma\'\n            ').fetchone()[0] or 0)
    standalone = float(conn.execute('\n            SELECT COALESCE(SUM(price), 0)\n            FROM drink_orders\n            WHERE session_id IS NULL\n              AND lower(COALESCE(item_type, \'drink\')) != \'buyurtma\'\n            ').fetchone()[0] or 0)
    conn.close()
    return float(session_time + ended_drinks + standalone)
def sessions_breakdown_for_day(day: str) -> List[dict[str, Any]]:
    """Kun bo\'yicha yakunlangan seanslar (PS / tovar / jostik ajratilgan).\n\n    Kassa jabıw bilan mos: jostik Playstation tu\'simiga, tovarlar alohida.\n    """
    start, end = business_day_bounds(day)
    conn = _connect()
    rows = conn.execute('\n        SELECT\n            s.id,\n            s.station_id,\n            s.start_time,\n            s.end_time,\n            s.duration_minutes,\n            COALESCE(s.revenue, 0) AS revenue,\n            COALESCE(s.is_vip, 0) AS is_vip,\n            COALESCE(s.note, \'\') AS note,\n            COALESCE((\n                SELECT SUM(d.price)\n                FROM drink_orders d\n                WHERE d.session_id = s.id\n                  AND lower(COALESCE(d.item_type, \'drink\')) IN (\'drink\', \'market\')\n            ), 0) AS drink_revenue,\n            COALESCE((\n                SELECT SUM(d.price)\n                FROM drink_orders d\n                WHERE d.session_id = s.id\n                  AND lower(COALESCE(d.item_type, \'\')) = \'joystick\'\n            ), 0) AS joystick_revenue,\n            COALESCE((\n                SELECT SUM(d.price)\n                FROM drink_orders d\n                WHERE d.session_id = s.id\n                  AND lower(COALESCE(d.item_type, \'\')) = \'buyurtma\'\n            ), 0) AS buyurtma_revenue\n        FROM sessions s\n        WHERE s.end_time IS NOT NULL AND s.end_time >= ? AND s.end_time < ?\n        ORDER BY s.end_time DESC\n        ', (start, end)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        goods = float(d.get('drink_revenue') or 0)
        joy = float(d.get('joystick_revenue') or 0)
        buy = float(d.get('buyurtma_revenue') or 0)
        total_rev = float(d.get('revenue') or 0)
        d['session_revenue'] = max(0.0, total_rev - goods - joy)
        d['joystick_revenue'] = joy
        d['buyurtma_revenue'] = buy
        out.append(d)
    return out
def get_session_by_id(session_id: int) -> Optional[dict[str, Any]]:
    """Bitta seans ma\'lumoti."""
    conn = _connect()
    try:
        row = conn.execute('\n            SELECT id, station_id, start_time, end_time, duration_minutes,\n                   COALESCE(revenue, 0) AS revenue, COALESCE(total_seconds, 0) AS total_seconds,\n                   COALESCE(is_vip, 0) AS is_vip, COALESCE(note, \'\') AS note,\n                   COALESCE(billing_rate, 0) AS billing_rate\n            FROM sessions WHERE id = ?\n            ', (int(session_id),)).fetchone()
    except sqlite3.OperationalError:
        row = conn.execute('\n            SELECT id, station_id, start_time, end_time, duration_minutes,\n                   COALESCE(revenue, 0) AS revenue, COALESCE(total_seconds, 0) AS total_seconds,\n                   COALESCE(is_vip, 0) AS is_vip, COALESCE(note, \'\') AS note\n            FROM sessions WHERE id = ?\n            ', (int(session_id),)).fetchone()
    conn.close()
    return dict(row) if row else None
def set_session_note(session_id: int, note: str) -> None:
    """Seans sipatlama (izoh) yangilash."""
    conn = _connect()
    conn.execute('UPDATE sessions SET note = ? WHERE id = ?', ((note or '').strip(), int(session_id)))
    conn.commit()
    conn.close()
def adjust_session_revenue(session_id: int, delta: float) -> None:
    """Yopilgan seans uliwmaliq summasini tovar o\'zgarishiga moslash."""
    delta = float(delta or 0)
    if not session_id or abs(delta) < 0.5:
        return None
    else:
        conn = _connect()
        conn.execute('\n        UPDATE sessions\n        SET revenue = MAX(0, COALESCE(revenue, 0) + ?)\n        WHERE id = ?\n        ', (delta, int(session_id)))
        conn.commit()
        conn.close()
def sold_products_for_day(day: Optional[str]=None) -> List[dict[str, Any]]:
    """Kunlik sotilgan tovarlar (ichimlik+market), rasm va qoldiq bilan."""
    day = day or current_business_date().isoformat()
    start, end = business_day_bounds(day)
    report = operator_report_between(start, end)
    drinks_cat = {(str(d.get('drink_name') or '').lower(), float(d.get('volume') or 0)): d for d in get_drink_prices()}
    markets_cat = {str(m.get('name') or '').lower(): m for m in get_market_products()}
    out = []
    for d in report.get('drinks') or []:
        name = str(d.get('name') or '')
        vol = float(d.get('volume') or 0)
        cat = drinks_cat.get((name.lower(), vol)) or drinks_cat.get((name.lower(), round(vol, 2)))
        qty_now = int(cat.get('quantity') or 0) if cat else 0
        sold = int(d.get('count') or 0)
        sold_total = float(d.get('total') or 0)
        out.append({'kind': 'drink', 'name': f'{name} {vol:g} L' if vol else name, 'raw_name': name, 'volume': vol, 'sold_count': sold, 'sold_total': sold_total, 'unit_price': sold_total / sold if sold else float((cat or {}).get('price') or 0), 'stock': qty_now, 'start_stock': qty_now + sold, 'image': (cat or {}).get('image')})
    for m in report.get('market') or []:
        name = str(m.get('name') or '')
        cat = markets_cat.get(name.lower())
        qty_now = int(cat.get('quantity') or 0) if cat else 0
        sold = int(m.get('count') or 0)
        sold_total = float(m.get('total') or 0)
        grams = float((cat or {}).get('grams') or m.get('volume') or 0)
        display = name
        if grams > 0 and f'{grams:g}' not in name:
            display = f'{name} {grams:g} gr'
        out.append({'kind': 'market', 'name': display, 'raw_name': name, 'volume': grams, 'sold_count': sold, 'sold_total': sold_total, 'unit_price': sold_total / sold if sold else float((cat or {}).get('price') or 0), 'stock': qty_now, 'start_stock': qty_now + sold, 'image': (cat or {}).get('image'), 'product_id': int((cat or {}).get('id') or 0) or None})
    out.sort(key=lambda x: str(x.get('name') or ''))
    return out
def list_product_sales(raw_name: str, *, kind: str='drink', volume: float=0, day: Optional[str]=None) -> List[dict[str, Any]]:
    """Mahsulot bo\'yicha sotuvlar tarixi (kun oralig\'ida) — yopilgan stol + BAR."""
    day = day or current_business_date().isoformat()
    start, end = business_day_bounds(day)
    item_type = 'market' if kind == 'market' else 'drink'
    period = (start, end, start, end)
    conn = _connect()
    if item_type == 'drink':
        drink_filt = _drink_orders_closed_or_walkin_sql("AND d.item_type = 'drink' AND d.drink_name = ? AND ABS(d.volume - ?) < 0.001")
        rows = conn.execute(f"\n            SELECT d.id, d.station_id, d.drink_name, d.volume, d.price,\n                   d.order_time, d.session_id, d.item_type\n            {drink_filt}\n            ORDER BY d.order_time DESC, d.id DESC\n            ", (raw_name, float(volume), *period)).fetchall()
    else:
        vol = float(volume or 0)
        if vol > 0:
            market_filt = _drink_orders_closed_or_walkin_sql("AND d.item_type = 'market' AND d.drink_name = ? AND (ABS(d.volume - ?) < 0.001 OR d.volume = 0 OR d.volume IS NULL)")
            rows = conn.execute(f"\n                SELECT d.id, d.station_id, d.drink_name, d.volume, d.price,\n                       d.order_time, d.session_id, d.item_type\n                {market_filt}\n                ORDER BY d.order_time DESC, d.id DESC\n                ", (raw_name, vol, *period)).fetchall()
        else:
            market_filt = _drink_orders_closed_or_walkin_sql("AND d.item_type = 'market' AND d.drink_name = ?")
            rows = conn.execute(f"\n                SELECT d.id, d.station_id, d.drink_name, d.volume, d.price,\n                       d.order_time, d.session_id, d.item_type\n                {market_filt}\n                ORDER BY d.order_time DESC, d.id DESC\n                ", (raw_name, *period)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def revenue_split_for_day(day: str) -> dict[str, float]:
    """Kun bo\'yicha yakunlangan tushumni 2 qismga ajratib qaytarish.\n\n    Active seanslar qo\'shilmaydi. Shu sabab YANGILASH bosilganda raqam o\'z-o\'zidan\n    o\'zgarmaydi; seans STOP qilingandan keyingina kunlik hisobga qo\'shiladi.\n    Kun chegarasi admin panelidagi KUN sozlamasiga qarab (masalan 06:00–05:59).\n    """
    start, end = business_day_bounds(day)
    conn = _connect()
    ended = conn.execute('\n        SELECT\n            s.id,\n            COALESCE(s.revenue, 0) AS revenue,\n            COALESCE((\n                SELECT SUM(d.price) FROM drink_orders d WHERE d.session_id = s.id\n                  AND lower(COALESCE(d.item_type, \'drink\')) != \'buyurtma\'\n            ), 0) AS drink_rev\n        FROM sessions s\n        WHERE s.end_time IS NOT NULL AND s.end_time >= ? AND s.end_time < ?\n        ', (start, end)).fetchall()
    ended_session_time = 0.0
    for r in ended:
        ended_session_time += max(0.0, float(r['revenue'] or 0) - float(r['drink_rev'] or 0))
    joystick_linked = float(conn.execute('\n            SELECT COALESCE(SUM(d.price), 0)\n            FROM drink_orders d\n            JOIN sessions s ON d.session_id = s.id\n            WHERE s.end_time IS NOT NULL AND s.end_time >= ? AND s.end_time < ?\n              AND lower(COALESCE(d.item_type, \'\')) = \'joystick\'\n            ', (start, end)).fetchone()[0] or 0)
    ended_drinks = float(conn.execute('\n            SELECT COALESCE(SUM(d.price), 0)\n            FROM drink_orders d\n            JOIN sessions s ON d.session_id = s.id\n            WHERE s.end_time IS NOT NULL AND s.end_time >= ? AND s.end_time < ?\n              AND lower(COALESCE(d.item_type, \'drink\')) IN (\'drink\', \'market\')\n            ', (start, end)).fetchone()[0] or 0)
    standalone_drinks = float(conn.execute('\n            SELECT COALESCE(SUM(price), 0)\n            FROM drink_orders\n            WHERE session_id IS NULL AND order_time >= ? AND order_time < ?\n              AND lower(COALESCE(item_type, \'drink\')) IN (\'drink\', \'market\')\n            ', (start, end)).fetchone()[0] or 0)
    conn.close()
    session_total = float(ended_session_time) + float(joystick_linked)
    drink_total = float(ended_drinks + standalone_drinks)
    total = float(session_total + drink_total)
    return {'total': total, 'session_total': session_total, 'drink_total': drink_total}
def get_active_session_id(station_id: str) -> Optional[int]:
    """Stolning hozirgi faol (tugallanmagan) seans ID-sini olish."""
    conn = _connect()
    row = conn.execute('SELECT id FROM sessions WHERE station_id = ? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1', (station_id,)).fetchone()
    conn.close()
    return row['id'] if row else None
def today_sessions_summary() -> List[dict[str, Any]]:
    start, end = business_day_bounds(current_business_date().isoformat())
    conn = _connect()
    rows = conn.execute('\n        SELECT station_id, start_time, end_time, duration_minutes, revenue\n        FROM sessions\n        WHERE end_time IS NOT NULL AND end_time >= ? AND end_time < ?\n        ORDER BY end_time DESC\n        ', (start, end)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def find_catalog_image(item_type: str, name: str, volume: float=0.0) -> Optional[bytes]:
    """Ichimlik/market katalogidan rasm (BLOB) topish."""
    kind = (item_type or '').strip().lower()
    nm = (name or '').strip()
    if not nm:
        return None
    conn = _connect()
    try:
        if kind == 'drink':
            row = conn.execute(
                '\n                SELECT image FROM drink_prices\n                WHERE drink_name = ? AND ABS(volume - ?) < 0.001\n                LIMIT 1\n                ',
                (nm, float(volume or 0)),
            ).fetchone()
            if row and row['image']:
                return bytes(row['image'])
            row = conn.execute('SELECT image FROM drink_prices WHERE drink_name = ? LIMIT 1', (nm,)).fetchone()
            if row and row['image']:
                return bytes(row['image'])
        if kind == 'market':
            row = conn.execute(
                '\n                SELECT image FROM market_products\n                WHERE name = ? AND ABS(grams - ?) < 0.001\n                ORDER BY id LIMIT 1\n                ',
                (nm, float(volume or 0)),
            ).fetchone()
            if row and row['image']:
                return bytes(row['image'])
            row = conn.execute('SELECT image FROM market_products WHERE name = ? ORDER BY id LIMIT 1', (nm,)).fetchone()
            if row and row['image']:
                return bytes(row['image'])
        return None
    finally:
        conn.close()
def get_drink_prices() -> List[dict[str, Any]]:
    """Barcha ichimlik narxlari ro\'yxati (rasm bilan)."""
    conn = _connect()
    rows = conn.execute('SELECT drink_name, volume, price, quantity, image, COALESCE(cost_price, 0) AS cost_price FROM drink_prices ORDER BY drink_name, volume').fetchall()
    conn.close()
    return [dict(r) for r in rows]
_BAR_ORDER_KEY = 'bar_product_order'
def bar_product_key(product: dict[str, Any]) -> str:
    """BAR kartochka uchun barqaror kalit."""
    kind = str(product.get('kind') or '')
    if kind == 'drink':
        return f"drink|{str(product.get('drink_name') or '').strip()}|{float(product.get('volume') or 0):g}"
    else:
        if kind == 'market':
            return f"market|{int(product.get('id') or 0)}"
        else:
            return ''
def get_bar_product_order() -> List[str]:
    raw = (_setting_get(_BAR_ORDER_KEY, '') or '').strip()
    if not raw:
        return []
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        else:
            return [str(x) for x in data if str(x).strip()]
def set_bar_product_order(keys: List[str]) -> None:
    cleaned = []
    seen = set()
    for key in keys:
        k = str(key or '').strip()
        if not k or k in seen:
            continue
        else:
            seen.add(k)
            cleaned.append(k)
    _setting_set(_BAR_ORDER_KEY, json.dumps(cleaned, ensure_ascii=False))
def sort_products_by_bar_order(products: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """Saqlangan BAR tartibi bo\'yicha saralash (yangi mahsulotlar oxiriga)."""
    order = get_bar_product_order()
    index = {k: i for i, k in enumerate(order)}
    decorated = []
    for i, p in enumerate(products):
        key = bar_product_key(p)
        rank = index.get(key, 10000 + i)
        decorated.append((rank, i, p))
    decorated.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in decorated]
def swap_bar_product_order(key_a: str, key_b: str, all_keys: List[str]) -> List[str]:
    """Ikki mahsulot o\'rnini almashtirib saqlaydi. Yangi tartibni qaytaradi."""
    keys = list(all_keys)
    order = keys[:]
    if key_a not in order:
        order.append(key_a)
    if key_b not in order:
        order.append(key_b)
    try:
        ia = order.index(key_a)
        ib = order.index(key_b)
    except ValueError:
        return order
    order[ia], order[ib] = (order[ib], order[ia])
    set_bar_product_order(order)
    return order
def set_drink_image(drink_name: str, volume: float, image: Optional[bytes]) -> None:
    """Ichimlik rasmini (BLOB) o\'rnatish yoki o\'chirish (None)."""
    conn = _connect()
    conn.execute('UPDATE drink_prices SET image = ? WHERE drink_name = ? AND volume = ?', (image, drink_name, volume))
    conn.commit()
    conn.close()
def get_drink_quantity(drink_name: str, volume: float) -> int:
    """Ichimlik qoldig\'i (dona)."""
    conn = _connect()
    row = conn.execute('SELECT quantity FROM drink_prices WHERE drink_name = ? AND volume = ?', (drink_name, volume)).fetchone()
    conn.close()
    if row is None:
        return 0
    else:
        return int(row[0] or 0)
def set_drink_price(drink_name: str, volume: float, price: float, quantity: Optional[int]=None, cost_price: Optional[float]=None) -> None:
    """Ichimlik narxini yangilash yoki qo\'shish. cost_price faqat ko\'rish uchun (hisobga ta\'sir qilmaydi)."""
    conn = _connect()
    if quantity is None and cost_price is None:
        conn.execute('\n            INSERT INTO drink_prices (drink_name, volume, price)\n            VALUES (?, ?, ?)\n            ON CONFLICT(drink_name, volume) DO UPDATE SET\n                price = excluded.price\n            ', (drink_name, volume, price))
    else:
        if cost_price is not None and quantity is None:
            conn.execute('\n            INSERT INTO drink_prices (drink_name, volume, price, cost_price)\n            VALUES (?, ?, ?, ?)\n            ON CONFLICT(drink_name, volume) DO UPDATE SET\n                price = excluded.price,\n                cost_price = excluded.cost_price\n            ', (drink_name, volume, price, float(max(0.0, cost_price))))
        else:
            if cost_price is None and quantity is not None:
                conn.execute('\n            INSERT INTO drink_prices (drink_name, volume, price, quantity)\n            VALUES (?, ?, ?, ?)\n            ON CONFLICT(drink_name, volume) DO UPDATE SET\n                price = excluded.price,\n                quantity = excluded.quantity\n            ', (drink_name, volume, price, max(0, int(quantity))))
            else:
                conn.execute('\n            INSERT INTO drink_prices (drink_name, volume, price, quantity, cost_price)\n            VALUES (?, ?, ?, ?, ?)\n            ON CONFLICT(drink_name, volume) DO UPDATE SET\n                price = excluded.price,\n                quantity = excluded.quantity,\n                cost_price = excluded.cost_price\n            ', (drink_name, volume, price, max(0, int(quantity or 0)), float(max(0.0, cost_price or 0))))
    conn.commit()
    conn.close()
def set_drink_cost_price(drink_name: str, volume: float, cost_price: float) -> None:
    """Faqat kelish narxini yangilash (sotish hisobiga ta\'sir qilmaydi)."""
    conn = _connect()
    conn.execute('UPDATE drink_prices SET cost_price = ? WHERE drink_name = ? AND volume = ?', (float(max(0.0, cost_price)), drink_name, volume))
    conn.commit()
    conn.close()
def set_drink_quantity(drink_name: str, volume: float, quantity: int) -> None:
    """Ichimlik sonini to\'g\'ridan-to\'g\'ri o\'rnatish."""
    conn = _connect()
    conn.execute('\n        UPDATE drink_prices SET quantity = ?\n        WHERE drink_name = ? AND volume = ?\n        ', (max(0, int(quantity)), drink_name, volume))
    conn.commit()
    conn.close()
def add_drink_stock(drink_name: str, volume: float, amount: int) -> int:
    """Omborga ichimlik qo\'shish. Yangi jami sonni qaytaradi."""
    if amount <= 0:
        return get_drink_quantity(drink_name, volume)
    else:
        conn = _connect()
        conn.execute('\n        UPDATE drink_prices SET quantity = quantity + ?\n        WHERE drink_name = ? AND volume = ?\n        ', (int(amount), drink_name, volume))
        row = conn.execute('SELECT quantity FROM drink_prices WHERE drink_name = ? AND volume = ?', (drink_name, volume)).fetchone()
        conn.commit()
        conn.close()
        return int(row[0] or 0) if row else 0
def delete_drink_price(drink_name: str, volume: float) -> None:
    """Ichimlik narxini o\'chirish (nom + hajm bo\'yicha)."""
    conn = _connect()
    conn.execute('DELETE FROM drink_prices WHERE drink_name = ? AND volume = ?', (drink_name, volume))
    conn.commit()
    conn.close()
def add_session_buyurtma(station_id: str, session_id: int, amount: float, note: str) -> int:
    """Ochiq seansga tashqi buyurtma (ombordan ayirilmaydi).\n\n    item_type=\'buyurtma\' — monitor/hisobda «Buyurtma» deb chiqadi.\n    """
    amount = round_to_thousand(amount)
    note = (note or '').strip()
    if amount <= 0:
        raise ValueError('Buyurtma summasi 0 dan katta bo\'lishi kerak.')
    else:
        if not note:
            raise ValueError('Buyurtma sipatlamasi bo\'sh bo\'lmasin.')
        else:
            if session_id is None:
                raise ValueError('Faol seans yo\'q.')
    conn = _connect()
    try:
        srow = conn.execute('SELECT id FROM sessions WHERE id = ? AND end_time IS NULL', (int(session_id),)).fetchone()
        if not srow:
            raise ValueError('Seans yopilgan yoki topilmadi.')
        else:
            now = _session_wall_now_iso()
            cur = conn.execute('\n            INSERT INTO drink_orders (station_id, drink_name, volume, price, order_time, session_id, item_type)\n            VALUES (?, ?, 0, ?, ?, ?, \'buyurtma\')\n            ', (station_id, note, amount, now, int(session_id)))
            conn.commit()
            return int(cur.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def add_drink_order(station_id: str, drink_name: str, volume: float, price: float, session_id: Optional[int]=None) -> None:
    """Yangi ichimlik buyurtmasi qo\'shish va ombordan 1 dona ayirish."""
    price = round_to_thousand(price)
    conn = _connect()
    try:
        row = conn.execute('SELECT quantity FROM drink_prices WHERE drink_name = ? AND volume = ?', (drink_name, volume)).fetchone()
        if row is None:
            raise ValueError(f'\'{drink_name}\' ({volume:g}L) ro\'yxatda topilmadi.')
        else:
            available = int(row[0] or 0)
            if available <= 0:
                raise ValueError(f'\'{drink_name}\' ({volume:g}L) omborda qolmagan! Qoldiq: 0 ta.')
            else:
                updated = conn.execute('\n            UPDATE drink_prices\n            SET quantity = quantity - 1\n            WHERE drink_name = ? AND volume = ? AND quantity > 0\n            ', (drink_name, volume))
                if updated.rowcount == 0:
                    raise ValueError(f'\'{drink_name}\' ({volume:g}L) omborda yetarli emas!')
                else:
                    now = _session_wall_now_iso()
                    conn.execute('\n            INSERT INTO drink_orders (station_id, drink_name, volume, price, order_time, session_id, item_type)\n            VALUES (?, ?, ?, ?, ?, ?, \'drink\')\n            ', (station_id, drink_name, volume, price, now, session_id))
                    if session_id is not None:
                        conn.execute('\n                UPDATE sessions\n                SET revenue = COALESCE(revenue, 0) + ?\n                WHERE id = ? AND end_time IS NOT NULL\n                ', (price, int(session_id)))
                    conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def get_station_drink_orders(station_id: str) -> List[dict[str, Any]]:
    """Stolning ichimlik buyurtmalari ro\'yxati."""
    conn = _connect()
    rows = conn.execute('\n        SELECT drink_name, volume, price, order_time\n        FROM drink_orders \n        WHERE station_id = ?\n        ORDER BY order_time DESC\n        ', (station_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def get_session_orders_grouped(session_id: Optional[int], station_id: Optional[str]=None) -> List[dict[str, Any]]:
    """Seansdagi (yoki seanssiz, stol bo\'yicha) buyurtmalarni nom+narx bo\'yicha\n    guruhlab, soni va jami summasi bilan qaytaradi.\n\n    Har bir element: {name, volume, price, item_type, count, total}\n    Jostiklar faol seansda vaqt bo\'yicha hisoblanadi.\n    """
    conn = _connect()
    session_active = False
    if session_id is not None:
        srow = conn.execute('SELECT end_time FROM sessions WHERE id = ?', (int(session_id),)).fetchone()
        session_active = bool(srow) and srow['end_time'] is None
        rows = conn.execute('\n            SELECT id, drink_name AS name, volume, price, item_type, order_time\n            FROM drink_orders\n            WHERE session_id = ?\n            ORDER BY item_type DESC, drink_name, id\n            ', (int(session_id),)).fetchall()
    else:
        if station_id is not None:
            rows = conn.execute('\n            SELECT id, drink_name AS name, volume, price, item_type, order_time\n            FROM drink_orders\n            WHERE station_id = ? AND session_id IS NULL\n            ORDER BY item_type DESC, drink_name, id\n            ', (station_id,)).fetchall()
        else:
            rows = []
    conn.close()
    try:
        from app.core.network_time import trusted_now_naive
        now = trusted_now_naive()
    except Exception:
        now = datetime.now()
    grouped = {}
    for r in rows:
        item_type = str(r['item_type'] or 'drink')
        name = r['name']
        volume = float(r['volume'] or 0)
        price = float(r['price'] or 0)
        if item_type == 'joystick':
            line_total = _joystick_line_amount(volume=volume, price=price, order_time=r['order_time'], session_active=session_active, until=now)
            unit = line_total
            key = ('joystick', name, r['id'])
            grouped[key] = {'name': name, 'volume': volume, 'price': unit, 'item_type': item_type, 'count': 1, 'total': line_total}
        else:
            if item_type == 'buyurtma':
                key = ('buyurtma', name, r['id'])
                grouped[key] = {'name': name, 'volume': 0.0, 'price': price, 'item_type': item_type, 'count': 1, 'total': price}
            else:
                key = (item_type, name, volume, price)
                item = grouped.get(key)
                if item is None:
                    grouped[key] = {'name': name, 'volume': volume, 'price': price, 'item_type': item_type, 'count': 1, 'total': price}
                else:
                    item['count'] += 1
                    item['total'] += price
    return list(grouped.values())
def get_station_drink_total(station_id: str, session_id: Optional[int]=None) -> float:
    """Stolning yoki ma\'lum bir seansning ichimlik/market/jostik jami summasi.\n\n    Faol seansdagi jostiklar soatbay (qo\'shilgan vaqtdan boshlab) hisoblanadi.\n    """
    conn = _connect()
    session_active = False
    if session_id is not None:
        srow = conn.execute('SELECT end_time FROM sessions WHERE id = ?', (int(session_id),)).fetchone()
        session_active = bool(srow) and srow['end_time'] is None
        rows = conn.execute('\n            SELECT volume, price, order_time, item_type\n            FROM drink_orders\n            WHERE session_id = ?\n            ', (int(session_id),)).fetchall()
    else:
        rows = conn.execute('\n            SELECT volume, price, order_time, item_type\n            FROM drink_orders\n            WHERE station_id = ? AND session_id IS NULL\n            ', (station_id,)).fetchall()
    conn.close()
    try:
        from app.core.network_time import trusted_now_naive
        now = trusted_now_naive()
    except Exception:
        now = datetime.now()
    total = 0.0
    for r in rows:
        if str(r['item_type'] or '') == 'joystick':
            total += _joystick_line_amount(volume=float(r['volume'] or 0), price=float(r['price'] or 0), order_time=r['order_time'], session_active=session_active, until=now)
        else:
            total += float(r['price'] or 0)
    return float(total)
def get_session_joystick_total(station_id: str, session_id: Optional[int]=None) -> float:
    """Faqat jostiklar summasi (ichimlik/market qo\'shilmaydi).\n\n    Jostik puli hisobda Playstation ustuniga qo\'shiladi, tovarlarga emas.\n    Summa har doim minglik, shu sababli uni tovarlardan ayirib Playstationga\n    qo\'shish jami summani o\'zgartirmaydi.\n    """
    conn = _connect()
    session_active = False
    if session_id is not None:
        srow = conn.execute('SELECT end_time FROM sessions WHERE id = ?', (int(session_id),)).fetchone()
        session_active = bool(srow) and srow['end_time'] is None
        rows = conn.execute('\n            SELECT volume, price, order_time\n            FROM drink_orders\n            WHERE session_id = ? AND item_type = \'joystick\'\n            ', (int(session_id),)).fetchall()
    else:
        rows = conn.execute('\n            SELECT volume, price, order_time\n            FROM drink_orders\n            WHERE station_id = ? AND session_id IS NULL AND item_type = \'joystick\'\n            ', (station_id,)).fetchall()
    conn.close()
    try:
        from app.core.network_time import trusted_now_naive
        now = trusted_now_naive()
    except Exception:
        now = datetime.now()
    total = 0.0
    for r in rows:
        total += _joystick_line_amount(volume=float(r['volume'] or 0), price=float(r['price'] or 0), order_time=r['order_time'], session_active=session_active, until=now)
    return float(total)
def get_session_buyurtma_total(station_id: str, session_id: Optional[int]=None) -> float:
    """Tashqi buyurtma summasi. Mijoz ekrani jamiga kiradi; kassa/daromad/tovarga kirmaydi."""
    conn = _connect()
    if session_id is not None:
        row = conn.execute('\n            SELECT COALESCE(SUM(price), 0)\n            FROM drink_orders\n            WHERE session_id = ? AND item_type = \'buyurtma\'\n            ', (int(session_id),)).fetchone()
    else:
        row = conn.execute('\n            SELECT COALESCE(SUM(price), 0)\n            FROM drink_orders\n            WHERE station_id = ? AND session_id IS NULL AND item_type = \'buyurtma\'\n            ', (station_id,)).fetchone()
    conn.close()
    return float(row[0] or 0) if row else 0.0
def split_session_charges(station_id: str, session_id: Optional[int]=None) -> tuple[float, float]:
    """Seans tovarlari va jostikni ajratadi.\n\n    Jostik — Playstation. Buyurtma kirmaydi (faqat mijoz jamida).\n    Qaytaradi: (tovarlar, jostik).\n    """
    all_amt = float(get_station_drink_total(station_id, session_id) or 0)
    joy = float(get_session_joystick_total(station_id, session_id) or 0)
    buy = float(get_session_buyurtma_total(station_id, session_id) or 0)
    return (max(0.0, all_amt - joy - buy), joy)
def get_returnable_orders_grouped(session_id: Optional[int], station_id: str) -> List[dict[str, Any]]:
    """Qaytarish uchun ichimlik/market/buyurtma guruhlari.\n\n    drink/market — omborga qaytadi; buyurtma — faqat o\'chiriladi.\n    """
    conn = _connect()
    if session_id is not None:
        rows = conn.execute('\n            SELECT\n                drink_name AS name,\n                volume,\n                price,\n                item_type,\n                COUNT(*) AS count,\n                SUM(price) AS total,\n                MAX(id) AS latest_order_id\n            FROM drink_orders\n            WHERE session_id = ? AND item_type IN (\'drink\', \'market\', \'buyurtma\')\n            GROUP BY drink_name, volume, price, item_type\n            ORDER BY\n                CASE item_type\n                    WHEN \'buyurtma\' THEN 0\n                    WHEN \'market\' THEN 1\n                    ELSE 2\n                END,\n                drink_name\n            ', (session_id,)).fetchall()
    else:
        rows = conn.execute('\n            SELECT\n                drink_name AS name,\n                volume,\n                price,\n                item_type,\n                COUNT(*) AS count,\n                SUM(price) AS total,\n                MAX(id) AS latest_order_id\n            FROM drink_orders\n            WHERE station_id = ? AND session_id IS NULL\n              AND item_type IN (\'drink\', \'market\', \'buyurtma\')\n            GROUP BY drink_name, volume, price, item_type\n            ORDER BY\n                CASE item_type\n                    WHEN \'buyurtma\' THEN 0\n                    WHEN \'market\' THEN 1\n                    ELSE 2\n                END,\n                drink_name\n            ', (station_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def cancel_order_and_return_stock(order_id: int) -> bool:
    """Bitta buyurtmani bekor qiladi.\n\n    drink/market — omborga 1 dona qaytaradi.\n    buyurtma — faqat yozuvni o\'chiradi (ombor yo\'q).\n    """
    conn = _connect()
    try:
        row = conn.execute(
            '\n            SELECT id, drink_name, volume, price, item_type, session_id\n            FROM drink_orders\n            WHERE id = ? AND item_type IN (\'drink\', \'market\', \'buyurtma\')\n            ',
            (int(order_id),),
        ).fetchone()
        if row is None:
            return False
        item_type = str(row['item_type'] or '')
        name = str(row['drink_name'] or '')
        volume = float(row['volume'] or 0)
        price = float(row['price'] or 0)
        session_id = row['session_id']
        restocked = False
        if item_type == 'buyurtma':
            conn.execute('DELETE FROM drink_orders WHERE id = ?', (int(order_id),))
            conn.commit()
            return True
        if item_type == 'drink':
            cur = conn.execute(
                '\n                UPDATE drink_prices\n                SET quantity = quantity + 1\n                WHERE drink_name = ? AND volume = ?\n                ',
                (name, volume),
            )
            restocked = int(cur.rowcount or 0) > 0
        elif item_type == 'market':
            cur = conn.execute(
                '\n                UPDATE market_products\n                SET quantity = quantity + 1\n                WHERE id = (\n                    SELECT id\n                    FROM market_products\n                    WHERE name = ? AND grams = ? AND ABS(price - ?) < 0.5\n                    ORDER BY id\n                    LIMIT 1\n                )\n                ',
                (name, volume, price),
            )
            if int(cur.rowcount or 0) <= 0:
                cur = conn.execute(
                    '\n                    UPDATE market_products\n                    SET quantity = quantity + 1\n                    WHERE id = (\n                        SELECT id\n                        FROM market_products\n                        WHERE name = ? AND grams = ?\n                        ORDER BY id\n                        LIMIT 1\n                    )\n                    ',
                    (name, volume),
                )
            restocked = int(cur.rowcount or 0) > 0
        if not restocked and item_type in ('drink', 'market'):
            conn.rollback()
            return False
        conn.execute('DELETE FROM drink_orders WHERE id = ?', (int(order_id),))
        if session_id is not None:
            conn.execute(
                '\n                UPDATE sessions\n                SET revenue = MAX(0, COALESCE(revenue, 0) - ?)\n                WHERE id = ? AND end_time IS NOT NULL\n                ',
                (price, int(session_id)),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def add_market_product(name: str, price: float, grams: float=0, quantity: int=0, image: Optional[bytes]=None, category: str='Oziq-ovqat', description: str='', cost_price: float=0) -> int:
    """Yangi market mahsuloti (yeydigan narsa) qo\'shish. Yangi id qaytaradi."""
    conn = _connect()
    cur = conn.execute('\n        INSERT INTO market_products (name, price, category, description, grams, quantity, image, cost_price)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n        ', (name, price, category, description, float(grams), max(0, int(quantity)), image, float(max(0.0, cost_price))))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return int(new_id)
def get_market_products() -> List[dict[str, Any]]:
    """Barcha market mahsulotlari ro\'yxati (rasm bilan)."""
    conn = _connect()
    rows = conn.execute('\n        SELECT id, name, price, category, description, grams, quantity, image,\n               COALESCE(cost_price, 0) AS cost_price\n        FROM market_products ORDER BY name\n        ').fetchall()
    conn.close()
    return [dict(r) for r in rows]
def get_market_product(product_id: int) -> Optional[dict[str, Any]]:
    """Bitta market mahsulotini olish."""
    conn = _connect()
    row = conn.execute('\n        SELECT id, name, price, category, description, grams, quantity, image,\n               COALESCE(cost_price, 0) AS cost_price\n        FROM market_products WHERE id = ?\n        ', (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
def update_market_product(product_id: int, name: Optional[str]=None, price: Optional[float]=None, grams: Optional[float]=None, quantity: Optional[int]=None, image: Optional[bytes]=None, update_image: bool=False, cost_price: Optional[float]=None) -> None:
    """Market mahsulotini yangilash. update_image=True bo\'lsa image qiymati (None bo\'lsa ham) yoziladi."""
    fields = []
    params = []
    if name is not None:
        fields.append('name = ?')
        params.append(name)
    if price is not None:
        fields.append('price = ?')
        params.append(float(price))
    if grams is not None:
        fields.append('grams = ?')
        params.append(float(grams))
    if quantity is not None:
        fields.append('quantity = ?')
        params.append(max(0, int(quantity)))
    if cost_price is not None:
        fields.append('cost_price = ?')
        params.append(float(max(0.0, cost_price)))
    if update_image:
        fields.append('image = ?')
        params.append(image)
    if not fields:
        return
    else:
        params.append(product_id)
        conn = _connect()
        conn.execute(f"UPDATE market_products SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        conn.close()
def delete_market_product(product_id: int) -> None:
    """Mahsulotni o\'chirish."""
    conn = _connect()
    conn.execute('DELETE FROM market_products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
def update_product_price(product_id: int, new_price: float) -> None:
    """Mahsulot narxini yangilash."""
    conn = _connect()
    conn.execute('UPDATE market_products SET price = ? WHERE id = ?', (new_price, product_id))
    conn.commit()
    conn.close()
def get_market_quantity(product_id: int) -> int:
    """Market mahsuloti qoldig\'i (dona)."""
    conn = _connect()
    row = conn.execute('SELECT quantity FROM market_products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return int(row[0] or 0) if row else 0
def set_market_quantity(product_id: int, quantity: int) -> None:
    """Market mahsuloti sonini to\'g\'ridan-to\'g\'ri o\'rnatish."""
    conn = _connect()
    conn.execute('UPDATE market_products SET quantity = ? WHERE id = ?', (max(0, int(quantity)), product_id))
    conn.commit()
    conn.close()
def add_market_stock(product_id: int, amount: int) -> int:
    """Market omboriga mahsulot qo\'shish. Yangi jami sonni qaytaradi."""
    if amount <= 0:
        return get_market_quantity(product_id)
    else:
        conn = _connect()
        conn.execute('UPDATE market_products SET quantity = quantity + ? WHERE id = ?', (int(amount), product_id))
        row = conn.execute('SELECT quantity FROM market_products WHERE id = ?', (product_id,)).fetchone()
        conn.commit()
        conn.close()
        return int(row[0] or 0) if row else 0
def add_market_order(station_id: str, product_id: int, session_id: Optional[int]=None, count: int=1) -> None:
    """Market mahsuloti sotuvi: ombordan ayirib, drink_orders ga (item_type=\'market\') yozadi.\n\n    Daromad hisoblari drink_orders orqali avtomatik ishlaydi (TOVARLAR ustuniga qo\'shiladi).\n    """
    if count <= 0:
        return
    else:
        conn = _connect()
        try:
            row = conn.execute('SELECT name, price, grams, quantity FROM market_products WHERE id = ?', (product_id,)).fetchone()
            if row is None:
                raise ValueError('Mahsulot ro\'yxatda topilmadi.')
            else:
                name = row['name']
                price = round_to_thousand(float(row['price']))
                grams = float(row['grams'] or 0)
                available = int(row['quantity'] or 0)
                if available < count:
                    raise ValueError(f'\'{name}\' omborda yetarli emas! Qoldiq: {available} ta.')
                else:
                    conn.execute('UPDATE market_products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?', (count, product_id, count))
                    if conn.execute('SELECT changes()').fetchone()[0] <= 0:
                        raise ValueError(f'\'{name}\' omborda yetarli emas! Qoldiq: {available} ta.')
                    else:
                        now = _session_wall_now_iso()
                        for _ in range(count):
                            conn.execute('\n                INSERT INTO drink_orders (station_id, drink_name, volume, price, order_time, session_id, item_type)\n                VALUES (?, ?, ?, ?, ?, ?, \'market\')\n                ', (station_id, name, grams, price, now, session_id))
                        if session_id is not None:
                            conn.execute('\n                UPDATE sessions\n                SET revenue = COALESCE(revenue, 0) + ?\n                WHERE id = ? AND end_time IS NOT NULL\n                ', (price * count, int(session_id)))
                        conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
def get_all_recent_orders(limit: int=50) -> List[dict[str, Any]]:
    """Barcha stollardan tushgan oxirgi buyurtmalar."""
    conn = _connect()
    rows = conn.execute('\n        SELECT station_id, drink_name, volume, price, order_time \n        FROM drink_orders \n        ORDER BY order_time DESC \n        LIMIT ?\n        ', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def get_detailed_daily_report(day: Optional[str]=None) -> List[dict[str, Any]]:
    """Berilgan biznes kunidagi yakunlangan sessiyalar va ularning ichimliklari."""
    conn = _connect()
    biz_day = day or current_business_date().isoformat()
    start, end = business_day_bounds(biz_day)
    query = '\n        SELECT s.id, s.station_id, s.start_time, s.end_time, s.duration_minutes, s.revenue,\n               (SELECT GROUP_CONCAT(d.drink_name, \', \')\n                FROM drink_orders d WHERE d.session_id = s.id) as drinks\n        FROM sessions s\n        WHERE s.end_time IS NOT NULL AND s.end_time >= ? AND s.end_time < ?\n        ORDER BY s.id DESC\n    '
    try:
        rows = conn.execute(query, (start, end)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f'Xatolik (Report): {e}')
        return []
    finally:
        conn.close()
def _drink_orders_closed_or_walkin_sql(item_type_filter: str='') -> str:
    """Yopilgan stol buyurtmalari + BAR (session_id NULL). Ochiq stol kirmaydi.\n\n    item_type_filter: \'\' | \"AND d.item_type = ?\" | \"AND d.item_type IN (...)\"\n    """
    type_clause = item_type_filter
    return f'\n        FROM drink_orders d\n        LEFT JOIN sessions s ON s.id = d.session_id\n        WHERE 1=1\n          {type_clause}\n          AND (\n                (d.session_id IS NOT NULL\n                 AND s.end_time IS NOT NULL\n                 AND s.end_time >= ? AND s.end_time < ?)\n             OR (d.session_id IS NULL\n                 AND d.order_time >= ? AND d.order_time < ?)\n          )\n    '
def operator_report_between(start_iso: str, end_iso: str) -> dict[str, Any]:
    """Berilgan vaqt oralig\'i uchun to\'liq hisobot (operator topshirig\'i uchun).\n\n    Qaytaradi: jami daromad, seans/ichimlik/market/jostik bo\'yicha summalar,\n    hamda ichimliklar va market mahsulotlari ro\'yxati (nom, dona, summa).\n\n    Tovarlar: faqat yopilgan stollar + BAR (DOKON) — ochiq stol buyurtmasi\n    STOP qilinmaguncha Satilg\'an / Kassa jabıwga kirmaydi.\n    """
    conn = _connect()
    try:
        ended = conn.execute('\n            SELECT\n                COALESCE(s.revenue, 0) AS revenue,\n                COALESCE((\n                    SELECT SUM(d.price) FROM drink_orders d WHERE d.session_id = s.id\n                      AND lower(COALESCE(d.item_type, \'drink\')) != \'buyurtma\'\n                ), 0) AS linked\n            FROM sessions s\n            WHERE s.end_time IS NOT NULL AND s.end_time >= ? AND s.end_time < ?\n            ', (start_iso, end_iso)).fetchall()
        session_total = 0.0
        for r in ended:
            session_total += max(0.0, float(r['revenue'] or 0) - float(r['linked'] or 0))
        period = (start_iso, end_iso, start_iso, end_iso)
        def _sum(item_type: str) -> float:
            row = conn.execute(f"\n                SELECT COALESCE(SUM(d.price), 0)\n                {_drink_orders_closed_or_walkin_sql('AND d.item_type = ?')}\n                ", (item_type, *period)).fetchone()
            return float(row[0] or 0)
        drink_total = _sum('drink')
        market_total = _sum('market')
        joystick_total = _sum('joystick')
        buyurtma_total = _sum('buyurtma')
        drink_list_sql = _drink_orders_closed_or_walkin_sql("AND d.item_type = 'drink'")
        market_list_sql = _drink_orders_closed_or_walkin_sql("AND d.item_type = 'market'")
        drinks = [dict(r) for r in conn.execute(f"\n                SELECT d.drink_name AS name, d.volume,\n                       COUNT(*) AS count, SUM(d.price) AS total\n                {drink_list_sql}\n                GROUP BY d.drink_name, d.volume, d.price\n                ORDER BY d.drink_name\n                ", period).fetchall()]
        market = [dict(r) for r in conn.execute(f"\n                SELECT d.drink_name AS name, d.volume,\n                       COUNT(*) AS count, SUM(d.price) AS total\n                {market_list_sql}\n                GROUP BY d.drink_name, d.volume, d.price\n                ORDER BY d.drink_name\n                ", period).fetchall()]
    finally:
        conn.close()
    total = session_total + drink_total + market_total + joystick_total
    return {'period_start': start_iso, 'period_end': end_iso, 'session_total': session_total, 'drink_total': drink_total, 'market_total': market_total, 'joystick_total': joystick_total, 'buyurtma_total': buyurtma_total, 'total': total, 'drinks': drinks, 'market': market}
def add_debtor(client_name: str, phone: str, amount: float, note: str='') -> int:
    """Yangi qarzdor yozuvi qo\'shish."""
    name = (client_name or '').strip()
    if not name:
        raise ValueError('Klient nomi kiritilmadi.')
    else:
        amount = round_to_thousand(amount)
        if amount <= 0:
            raise ValueError('Qarz miqdori 0 dan katta bo\'lishi kerak (minglik).')
        else:
            conn = _connect()
            now = _session_wall_now_iso()
            cur = conn.execute('\n        INSERT INTO debtors (client_name, phone, amount, debt_time, note, paid)\n        VALUES (?, ?, ?, ?, ?, 0)\n        ', (name, (phone or '').strip(), amount, now, (note or '').strip()))
            conn.commit()
            new_id = int(cur.lastrowid)
            conn.close()
            return new_id
def list_debtors(search: str='', day: Optional[str]=None, include_paid: bool=False) -> List[dict[str, Any]]:
    """Qarzdorlar ro\'yxati. day YYYY-MM-DD bo\'lsa shu kun bo\'yicha filter."""
    conn = _connect()
    clauses = []
    params = []
    if not include_paid:
        clauses.append('paid = 0')
    q = (search or '').strip()
    if q:
        clauses.append('(client_name LIKE ? OR phone LIKE ? OR note LIKE ?)')
        like = f'%{q}%'
        params.extend([like, like, like])
    if day:
        clauses.append('date(debt_time) = ?')
        params.append(day)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    rows = conn.execute(f'\n        SELECT id, client_name, phone, amount, debt_time, note, paid, paid_time\n        FROM debtors\n        {where}\n        ORDER BY debt_time DESC, id DESC\n        ', params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def debtor_day_summary(include_paid: bool=False) -> List[dict[str, Any]]:
    """Chap panel uchun kunlar bo\'yicha qarz jami."""
    conn = _connect()
    where = '' if include_paid else 'WHERE paid = 0'
    rows = conn.execute(f'\n        SELECT date(debt_time) AS day, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count\n        FROM debtors\n        {where}\n        GROUP BY date(debt_time)\n        ORDER BY day DESC\n        ').fetchall()
    conn.close()
    return [dict(r) for r in rows]
def debtor_total_between(start_iso: str, end_iso: str, include_paid: bool=True) -> float:
    """Shu oraliqda YARATILGAN qarizlar jami (asl yozilgan summa).\n\n    include_paid default True — kassa uchun: to\'langan bo\'lsa ham QARIZLAR ga kiradi.\n    """
    conn = _connect()
    where_paid = '' if include_paid else 'AND d.paid = 0'
    row = conn.execute(f'\n        SELECT COALESCE(SUM(\n            COALESCE(d.amount, 0) + COALESCE((\n                SELECT SUM(e.amount) FROM debt_payment_events e WHERE e.debtor_id = d.id\n            ), 0)\n        ), 0)\n        FROM debtors d\n        WHERE d.debt_time >= ? AND d.debt_time < ? {where_paid}\n        ', (start_iso, end_iso)).fetchone()
    conn.close()
    return float(row[0] or 0)
def record_debt_payment(amount: float, *, debtor_id: Optional[int]=None, client_name: str='', phone: str='', note: str='', paid_time: Optional[str]=None) -> int:
    """Qarz to\'lovi hodisasini yozish (Kassa: Qarzin to\'legenler)."""
    amt = float(amount or 0)
    if amt <= 0:
        return 0
    else:
        when = (paid_time or _session_wall_now_iso()).strip()
        conn = _connect()
        cur = conn.execute('\n        INSERT INTO debt_payment_events (debtor_id, client_name, phone, amount, paid_time, note)\n        VALUES (?, ?, ?, ?, ?, ?)\n        ', (int(debtor_id) if debtor_id else None, (client_name or '').strip(), (phone or '').strip(), amt, when, (note or '').strip()))
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id
def debtor_paid_total_between(start_iso: str, end_iso: str) -> float:
    """Shu oraliqda to\'langan qarzlar jami (to\'lov hodisalari + eski paid yozuvlar)."""
    conn = _connect()
    events = float(conn.execute('\n            SELECT COALESCE(SUM(amount), 0)\n            FROM debt_payment_events\n            WHERE paid_time >= ? AND paid_time < ?\n            ', (start_iso, end_iso)).fetchone()[0] or 0)
    legacy = float(conn.execute('\n            SELECT COALESCE(SUM(d.amount), 0)\n            FROM debtors d\n            WHERE d.paid = 1 AND d.paid_time IS NOT NULL\n              AND d.paid_time >= ? AND d.paid_time < ?\n              AND d.amount > 0\n              AND NOT EXISTS (\n                  SELECT 1 FROM debt_payment_events e\n                  WHERE e.debtor_id = d.id\n              )\n            ', (start_iso, end_iso)).fetchone()[0] or 0)
    conn.close()
    return events + legacy
def adjust_debtor_amount(debtor_id: int, delta: float) -> float:
    """Qarz miqdorini qo\'shish/kamaytirish. Kamaytirish = to\'lov (events ga yoziladi)."""
    delta = as_thousand(delta)
    if delta == 0:
        row = list_debtors(include_paid=True)
        for item in row:
            if int(item.get('id', 0)) == int(debtor_id):
                return float(item.get('amount', 0) or 0)
        return 0.0
    conn = _connect()
    try:
        row = conn.execute('SELECT id, client_name, phone, amount, paid FROM debtors WHERE id = ?', (int(debtor_id),)).fetchone()
        if row is None:
            raise ValueError('Qarzdor topilmadi.')
        else:
            old_amount = float(row['amount'] or 0)
            new_amount = max(0.0, round_to_thousand(old_amount + delta))
            paid_now = None
            paid_flag = int(row['paid'] or 0)
            if delta < 0:
                paid_amt = round_to_thousand(min(old_amount, -delta))
                if paid_amt > 0:
                    when = _session_wall_now_iso()
                    conn.execute('\n                    INSERT INTO debt_payment_events\n                        (debtor_id, client_name, phone, amount, paid_time, note)\n                    VALUES (?, ?, ?, ?, ?, ?)\n                    ', (int(debtor_id), str(row['client_name'] or ''), str(row['phone'] or ''), paid_amt, when, 'qisman to\'lov' if new_amount > 0 else 'to\'liq to\'lov'))
                    if new_amount <= 0:
                        paid_flag = 1
                        paid_now = when
            conn.execute('UPDATE debtors SET amount = ?, paid = ?, paid_time = COALESCE(?, paid_time) WHERE id = ?', (new_amount, paid_flag, paid_now, int(debtor_id)))
            conn.commit()
            return new_amount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def mark_debtor_paid(debtor_id: int, paid: bool=True) -> None:
    """Qarzni to\'landi/to\'lanmadi. To\'langanda summa Qarzin to\'legenlerga yoziladi."""
    conn = _connect()
    try:
        row = conn.execute('SELECT id, client_name, phone, amount, paid FROM debtors WHERE id = ?', (int(debtor_id),)).fetchone()
        if row is None:
            raise ValueError('Qarzdor topilmadi.')
        else:
            if paid:
                amt = float(row['amount'] or 0)
                when = _session_wall_now_iso()
                if amt > 0 and (not int(row['paid'] or 0)):
                        conn.execute('\n                    INSERT INTO debt_payment_events\n                        (debtor_id, client_name, phone, amount, paid_time, note)\n                    VALUES (?, ?, ?, ?, ?, ?)\n                    ', (int(debtor_id), str(row['client_name'] or ''), str(row['phone'] or ''), amt, when, 'to\'liq to\'lov'))
                conn.execute('UPDATE debtors SET paid = 1, paid_time = ?, amount = 0 WHERE id = ?', (when, int(debtor_id)))
            else:
                pay = conn.execute('\n                SELECT id, amount FROM debt_payment_events\n                WHERE debtor_id = ?\n                ORDER BY id DESC LIMIT 1\n                ', (int(debtor_id),)).fetchone()
                restore_amt = float(row['amount'] or 0)
                if pay is not None:
                    restore_amt = max(restore_amt, float(pay['amount'] or 0))
                    conn.execute('DELETE FROM debt_payment_events WHERE id = ?', (int(pay['id']),))
                if restore_amt <= 0:
                    restore_amt = float(row['amount'] or 0)
                conn.execute('UPDATE debtors SET paid = 0, paid_time = NULL, amount = ? WHERE id = ?', (restore_amt, int(debtor_id)))
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def pay_client_debts(client_name: str, phone: str='', amount: Optional[float]=None) -> float:
    """Klientning ochiq qarizlarini to\'lash. Qaytadi: to\'langan jami."""
    name = (client_name or '').strip()
    phone_n = (phone or '').strip()
    open_rows = [r for r in list_debtors('', include_paid=False) if str(r.get('client_name') or '') == name and str(r.get('phone') or '') == phone_n]
    if not open_rows:
        return 0.0
    else:
        remaining = None if amount is None else round_to_thousand(amount)
        paid_total = 0.0
        for r in sorted(open_rows, key=lambda x: str(x.get('debt_time') or '')):
            due = float(r.get('amount') or 0)
            if due <= 0:
                mark_debtor_paid(int(r['id']), True)
            else:
                if remaining is None:
                    mark_debtor_paid(int(r['id']), True)
                    paid_total += due
                else:
                    if remaining <= 0:
                        break
                    else:
                        pay = round_to_thousand(min(due, remaining))
                        if pay <= 0:
                            break
                        else:
                            if pay >= due:
                                mark_debtor_paid(int(r['id']), True)
                            else:
                                adjust_debtor_amount(int(r['id']), -pay)
                            paid_total += pay
                            remaining -= pay
        return paid_total
def _clean_client_fields(name: str, phone: str='') -> tuple[str, str]:
    """Ism va telefonni ajratib tozalash (DB qatlami)."""
    name = (name or '').strip()
    phone = (phone or '').strip()
    parts = [p.strip() for p in name.replace(' - ', ' — ').split(' — ') if p.strip()]
    name_parts = []
    phones = []
    for p in parts:
        digits = ''.join((ch for ch in p if ch.isdigit()))
        if len(digits) >= 7:
            phones.append(''.join((ch for ch in p if ch.isdigit() or ch in '+')))
        else:
            name_parts.append(p)
    clean_name = name_parts[0] if name_parts else ''
    if not phone and phones:
        phone = phones[0]
    else:
        if phone:
            phone = ''.join((ch for ch in phone if ch.isdigit() or ch in '+'))
    if not clean_name:
        digits = ''.join((ch for ch in name if ch.isdigit()))
        if len(digits) >= 7:
            phone = phone or ''.join((ch for ch in name if ch.isdigit() or ch in '+'))
            clean_name = ''
    return (clean_name, phone)
def _booking_has_conflict(station_id: str, booking_time: str, *, exclude_id: Optional[int]=None, window_minutes: int=120) -> bool:
    """Bir stolda yaqin vaqtda boshqa faol bron bormi."""
    when = _parse_order_dt(booking_time)
    if when is None or not (station_id or '').strip():
        return False
    else:
        delta = timedelta(minutes=max(15, int(window_minutes)))
        start = (when - delta).isoformat(timespec='seconds')
        end = (when + delta).isoformat(timespec='seconds')
        conn = _connect()
        try:
            params = [station_id.strip(), start, end]
            sql = '\n            SELECT id FROM bookings\n            WHERE status = \'active\'\n              AND station_id = ?\n              AND booking_time >= ? AND booking_time <= ?\n        '
            if exclude_id is not None:
                sql += ' AND id != ?'
                params.append(int(exclude_id))
            sql += ' LIMIT 1'
            row = conn.execute(sql, params).fetchone()
            return row is not None
        finally:
            conn.close()
def add_booking(client_name: str, phone: str, station_id: str, booking_time: str, note: str='') -> int:
    """Yangi bron yozuvi qo\'shish."""
    name, phone_c = _clean_client_fields(client_name, phone)
    if not name:
        raise ValueError('Klient nomi kiritilmadi.')
    else:
        when = (booking_time or '').strip()
        if not when:
            when = datetime.now().isoformat(timespec='seconds')
        sid = (station_id or '').strip()
        if sid and _booking_has_conflict(sid, when):
            raise ValueError(f'{sid} stolida shu vaqt atrofida boshqa bron bor (±2 soat).')
        else:
            conn = _connect()
            cur = conn.execute('\n        INSERT INTO bookings (client_name, phone, station_id, booking_time, note, status, created_time)\n        VALUES (?, ?, ?, ?, ?, \'active\', ?)\n        ', (name, phone_c, sid, when, (note or '').strip(), datetime.now().isoformat(timespec='seconds')))
            conn.commit()
            new_id = int(cur.lastrowid)
            conn.close()
            return new_id
def update_booking(booking_id: int, *, client_name: Optional[str]=None, phone: Optional[str]=None, station_id: Optional[str]=None, booking_time: Optional[str]=None, note: Optional[str]=None) -> None:
    """Bronni tahrirlash."""
    conn = _connect()
    row = conn.execute('SELECT * FROM bookings WHERE id = ?', (int(booking_id),)).fetchone()
    if row is None:
        conn.close()
        raise ValueError('Bron topilmadi.')
    else:
        cur_name = str(row['client_name'] or '')
        cur_phone = str(row['phone'] or '')
        if client_name is not None or phone is not None:
            cur_name, cur_phone = _clean_client_fields(cur_name if client_name is None else client_name, cur_phone if phone is None else phone)
        fields = {'client_name': cur_name, 'phone': cur_phone, 'station_id': (station_id if station_id is not None else str(row['station_id'] or '')).strip(), 'booking_time': (booking_time if booking_time is not None else str(row['booking_time'] or '')).strip(), 'note': (note if note is not None else str(row['note'] or '')).strip()}
        if not fields['client_name']:
            conn.close()
            raise ValueError('Klient nomi kiritilmadi.')
        else:
            conn.close()
            if fields['station_id'] and _booking_has_conflict(fields['station_id'], fields['booking_time'], exclude_id=int(booking_id)):
                raise ValueError(f"{fields['station_id']} stolida shu vaqt atrofida boshqa bron bor (±2 soat).")
            else:
                conn = _connect()
                conn.execute('\n        UPDATE bookings\n        SET client_name = ?, phone = ?, station_id = ?, booking_time = ?, note = ?\n        WHERE id = ?\n        ', (fields['client_name'], fields['phone'], fields['station_id'], fields['booking_time'], fields['note'], int(booking_id)))
                conn.commit()
                conn.close()
def delete_booking(booking_id: int) -> None:
    """Bronni o\'chirish."""
    conn = _connect()
    conn.execute('DELETE FROM bookings WHERE id = ?', (int(booking_id),))
    conn.commit()
    conn.close()
def list_bookings(search: str='', include_closed: bool=False) -> List[dict[str, Any]]:
    """Bronlar ro\'yxati."""
    conn = _connect()
    clauses = []
    params = []
    if not include_closed:
        clauses.append('status = \'active\'')
    q = (search or '').strip()
    if q:
        clauses.append('(client_name LIKE ? OR phone LIKE ? OR station_id LIKE ? OR note LIKE ?)')
        like = f'%{q}%'
        params.extend([like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    rows = conn.execute(f'\n        SELECT id, client_name, phone, station_id, booking_time, note, status, created_time\n        FROM bookings\n        {where}\n        ORDER BY booking_time DESC, id DESC\n        ', params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        name, phone = _clean_client_fields(str(d.get('client_name') or ''), str(d.get('phone') or ''))
        d['client_name'] = name
        d['phone'] = phone
        out.append(d)
    return out
def active_bookings_by_station() -> dict[str, dict[str, Any]]:
    """Har bir stol uchun eng yaqin faol bron (station_id -> booking).\n\n    station_id maydonida ba\'zan ko\'rinadigan nom saqlangan bo\'lishi mumkin —\n    shunda ham matching qilinadi.\n    """
    name_to_id = {}
    try:
        for sid in list_station_ids():
            name_to_id[str(get_station_display_name(sid)).strip().lower()] = sid
            name_to_id[sid.strip().lower()] = sid
    except Exception:
        pass
    out = {}
    for b in list_bookings('', include_closed=False):
        raw = str(b.get('station_id') or '').strip()
        if not raw:
            continue
        else:
            sid = name_to_id.get(raw.lower(), raw)
            prev = out.get(sid)
            if prev is None:
                out[sid] = b
            else:
                try:
                    if str(b.get('booking_time') or '') < str(prev.get('booking_time') or ''):
                        out[sid] = b
                except Exception:
                    continue
    return out
def close_booking(booking_id: int) -> None:
    """Bronni yakunlangan holatga o\'tkazish."""
    conn = _connect()
    conn.execute('UPDATE bookings SET status = \'closed\' WHERE id = ?', (int(booking_id),))
    conn.commit()
    conn.close()
_EXPENSE_WORKER_NAMES_KEY = 'expense_worker_names'
_EXPENSE_CUSTOM_TYPES_KEY = 'expense_custom_types'
def _load_name_list(key: str) -> List[str]:
    raw = (_setting_get(key, '') or '').strip()
    if not raw:
        return []
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        else:
            out = []
            seen = set()
            for item in data:
                name = str(item or '').strip()
                if not name:
                    continue
                else:
                    low = name.casefold()
                    if low in seen:
                        continue
                    else:
                        seen.add(low)
                        out.append(name)
            return out
def _save_name_list(key: str, names: List[str]) -> None:
    cleaned = []
    seen = set()
    for item in names:
        name = str(item or '').strip()
        if not name:
            continue
        else:
            low = name.casefold()
            if low in seen:
                continue
            else:
                seen.add(low)
                cleaned.append(name)
    _setting_set(key, json.dumps(cleaned, ensure_ascii=False))
def list_expense_worker_names() -> List[str]:
    """Jumishshi aylig\'i uchun saqlangan ismlar (avto-to\'ldirish)."""
    return _load_name_list(_EXPENSE_WORKER_NAMES_KEY)
def remember_expense_worker_name(name: str) -> None:
    name = (name or '').strip()
    if not name:
        return
    else:
        names = list_expense_worker_names()
        low = name.casefold()
        names = [n for n in names if n.casefold() != low]
        names.insert(0, name)
        _save_name_list(_EXPENSE_WORKER_NAMES_KEY, names[:80])
def list_expense_custom_types() -> List[str]:
    """Qo\'lda kiritilgan qa\'rejet turlari (avto-to\'ldirish)."""
    return _load_name_list(_EXPENSE_CUSTOM_TYPES_KEY)
def remember_expense_custom_type(name: str) -> None:
    name = (name or '').strip()
    if not name:
        return
    else:
        names = list_expense_custom_types()
        low = name.casefold()
        names = [n for n in names if n.casefold() != low]
        names.insert(0, name)
        _save_name_list(_EXPENSE_CUSTOM_TYPES_KEY, names[:80])
def add_expense(expense_type: str, amount: float, wallet: str='cash', note: str='') -> int:
    """Yangi xarajat yozuvi qo\'shish. Ceyf (safe) dan chiqsa balans kamayadi."""
    etype = (expense_type or '').strip()
    if not etype:
        raise ValueError('Qa\'rejet turi kiritilmadi.')
    else:
        amount = round_to_thousand(amount)
        if amount <= 0:
            raise ValueError('Summa 0 dan katta bo\'lishi kerak (minglik).')
        else:
            wallet_value = (wallet or 'cash').strip() or 'cash'
            purge_old_expenses(30)
            conn = _connect()
            cur = conn.execute('\n        INSERT INTO expenses (expense_type, amount, wallet, note, created_time)\n        VALUES (?, ?, ?, ?, ?)\n        ', (etype, amount, wallet_value, (note or '').strip(), _session_wall_now_iso()))
            conn.commit()
            new_id = int(cur.lastrowid)
            conn.close()
            if wallet_value.lower() in ['safe', 'ceyf', 'сейф']:
                add_to_safe_balance(-amount)
            return new_id
def purge_old_expenses(keep_days: int=30) -> int:
    """1 oydan eski xarajatlarni o\'chirish.\n\n    Ochilgan kassa davridagi yozuvlar saqlanadi (jabıw hisobi buzilmasin).\n    """
    cutoff = (datetime.now() - timedelta(days=max(1, int(keep_days)))).isoformat(timespec='seconds')
    try:
        period = get_cash_period_start()
        if period and period < cutoff:
                cutoff = period
    except Exception:
        pass
    conn = _connect()
    cur = conn.execute('DELETE FROM expenses WHERE created_time < ?', (cutoff,))
    conn.commit()
    n = int(cur.rowcount or 0)
    conn.close()
    return n
def list_expenses(search: str='', day: Optional[str]=None, *, since: Optional[str]=None, until: Optional[str]=None, keep_days: Optional[int]=None) -> List[dict[str, Any]]:
    """Xarajatlar ro\'yxati.\n\n    day — aniq kun (YYYY-MM-DD).\n    since/until — ISO oralig\' (until exclusive).\n    keep_days — berilsa eski yozuvlar avval tozalanadi.\n    """
    if keep_days is not None:
        purge_old_expenses(int(keep_days))
    conn = _connect()
    clauses = []
    params = []
    q = (search or '').strip()
    if q:
        clauses.append('(expense_type LIKE ? OR wallet LIKE ? OR note LIKE ?)')
        like = f'%{q}%'
        params.extend([like, like, like])
    if day:
        clauses.append('date(created_time) = ?')
        params.append(day)
    if since:
        clauses.append('created_time >= ?')
        params.append(since)
    if until:
        clauses.append('created_time < ?')
        params.append(until)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    rows = conn.execute(f'\n        SELECT id, expense_type, amount, wallet, note, created_time\n        FROM expenses\n        {where}\n        ORDER BY created_time DESC, id DESC\n        ', params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def list_current_period_expenses(search: str='') -> List[dict[str, Any]]:
    """Joriy kassa davridagi xarajatlar (jabıwdan keyin bo\'sh)."""
    start, end = cash_period_bounds()
    return list_expenses(search, since=start, until=end)
def expense_day_summary(keep_days: int=30) -> List[dict[str, Any]]:
    """Chap panel: oxirgi N kunlik xarajatlar jami (faqat kassa — jabıw bilan mos)."""
    purge_old_expenses(keep_days)
    cutoff_day = (datetime.now() - timedelta(days=max(1, int(keep_days)))).date().isoformat()
    conn = _connect()
    rows = conn.execute('\n        SELECT date(created_time) AS day,\n               COALESCE(SUM(amount), 0) AS total,\n               COUNT(*) AS count\n        FROM expenses\n        WHERE date(created_time) >= ?\n          AND lower(COALESCE(NULLIF(trim(wallet), \'\'), \'cash\')) NOT IN (\'safe\', \'ceyf\')\n        GROUP BY date(created_time)\n        ORDER BY day DESC\n        ', (cutoff_day,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def expense_total_between(start_iso: str, end_iso: str, wallet: Optional[str]='cash') -> float:
    """Berilgan vaqt oralig\'idagi xarajatlar jami.\n\n    wallet=\'cash\' — faqat kassa (kassa jabıw / expected uchun).\n    wallet=\'safe\' — faqat Ceyf.\n    wallet=None — barcha.\n    """
    conn = _connect()
    if wallet is None:
        row = conn.execute('\n            SELECT COALESCE(SUM(amount), 0)\n            FROM expenses\n            WHERE created_time >= ? AND created_time < ?\n            ', (start_iso, end_iso)).fetchone()
    else:
        if str(wallet).lower() in ['safe', 'ceyf']:
            row = conn.execute('\n            SELECT COALESCE(SUM(amount), 0)\n            FROM expenses\n            WHERE created_time >= ? AND created_time < ?\n              AND lower(wallet) IN (\'safe\', \'ceyf\')\n            ', (start_iso, end_iso)).fetchone()
        else:
            row = conn.execute('\n            SELECT COALESCE(SUM(amount), 0)\n            FROM expenses\n            WHERE created_time >= ? AND created_time < ?\n              AND lower(COALESCE(NULLIF(trim(wallet), \'\'), \'cash\')) NOT IN (\'safe\', \'ceyf\')\n            ', (start_iso, end_iso)).fetchone()
    conn.close()
    return float(row[0] or 0)
def purge_old_clicks(keep_days: int=7) -> int:
    """1 haftadan eski CLICK yozuvlarini o\'chirish.\n\n    Ochilgan kassa davridagi CLICK lar saqlanadi (jabıw farqi buzilmasin).\n    """
    cutoff = (datetime.now() - timedelta(days=max(1, int(keep_days)))).isoformat(timespec='seconds')
    try:
        period = get_cash_period_start()
        if period and period < cutoff:
                cutoff = period
    except Exception:
        pass
    conn = _connect()
    cur = conn.execute('DELETE FROM click_entries WHERE created_time < ?', (cutoff,))
    conn.commit()
    n = int(cur.rowcount or 0)
    conn.close()
    return n
def add_click(amount: float) -> int:
    """Yangi CLICK summasi."""
    amount = round_to_thousand(amount)
    if amount <= 0:
        raise ValueError('CLICK summasi 0 dan katta bo\'lishi kerak (minglik).')
    else:
        purge_old_clicks(7)
        conn = _connect()
        cur = conn.execute('\n        INSERT INTO click_entries (amount, created_time)\n        VALUES (?, ?)\n        ', (amount, _session_wall_now_iso()))
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id
def delete_click(click_id: int) -> bool:
    """Bitta CLICK yozuvini o\'chirish."""
    conn = _connect()
    cur = conn.execute('DELETE FROM click_entries WHERE id = ?', (int(click_id),))
    conn.commit()
    n = int(cur.rowcount or 0)
    conn.close()
    return n > 0
def list_clicks(keep_days: int=7) -> List[dict[str, Any]]:
    """Oxirgi N kunlik CLICK yozuvlari (yangi → eski)."""
    purge_old_clicks(keep_days)
    cutoff = (datetime.now() - timedelta(days=max(1, int(keep_days)))).isoformat(timespec='seconds')
    conn = _connect()
    rows = conn.execute('\n        SELECT id, amount, created_time\n        FROM click_entries\n        WHERE created_time >= ?\n        ORDER BY created_time DESC, id DESC\n        ', (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def click_total_between(start_iso: str, end_iso: str) -> float:
    """Vaqt oralig\'idagi CLICK jami."""
    purge_old_clicks(7)
    conn = _connect()
    row = conn.execute('\n        SELECT COALESCE(SUM(amount), 0)\n        FROM click_entries\n        WHERE created_time >= ? AND created_time < ?\n        ', (start_iso, end_iso)).fetchone()
    conn.close()
    return float(row[0] or 0)
def click_total_for_cash_period() -> float:
    """Joriy kassa davridagi CLICK jami."""
    start, end = cash_period_bounds()
    return click_total_between(start, end)
def list_expenses_between(start_iso: str, end_iso: str) -> List[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute('\n        SELECT id, expense_type, amount, wallet, note, created_time\n        FROM expenses\n        WHERE created_time >= ? AND created_time < ?\n        ORDER BY created_time ASC, id ASC\n        ', (start_iso, end_iso)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def list_debtors_between(start_iso: str, end_iso: str) -> List[dict[str, Any]]:
    """Shu oraliqda yozilgan qarizlar (asl yozilgan summa bilan)."""
    conn = _connect()
    rows = conn.execute('\n        SELECT d.id, d.client_name, d.phone, d.amount, d.debt_time, d.note, d.paid, d.paid_time,\n               COALESCE((\n                   SELECT SUM(e.amount) FROM debt_payment_events e WHERE e.debtor_id = d.id\n               ), 0) AS paid_sum\n        FROM debtors d\n        WHERE d.debt_time >= ? AND d.debt_time < ?\n        ORDER BY d.debt_time ASC, d.id ASC\n        ', (start_iso, end_iso)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        issued = float(d.get('amount') or 0) + float(d.get('paid_sum') or 0)
        d['amount'] = issued
        d['remaining'] = float(r['amount'] or 0)
        out.append(d)
    return out
def list_debt_payments_between(start_iso: str, end_iso: str) -> List[dict[str, Any]]:
    """Shu oraliqda to\'langan qarizlar (to\'lov hodisalari)."""
    conn = _connect()
    rows = conn.execute('\n        SELECT id, debtor_id, client_name, phone, amount, paid_time, note\n        FROM debt_payment_events\n        WHERE paid_time >= ? AND paid_time < ?\n        ORDER BY paid_time ASC, id ASC\n        ', (start_iso, end_iso)).fetchall()
    legacy = conn.execute('\n        SELECT d.id, d.id AS debtor_id, d.client_name, d.phone, d.amount, d.paid_time AS paid_time, d.note\n        FROM debtors d\n        WHERE d.paid = 1 AND d.paid_time IS NOT NULL\n          AND d.paid_time >= ? AND d.paid_time < ?\n          AND d.amount > 0\n          AND NOT EXISTS (\n              SELECT 1 FROM debt_payment_events e WHERE e.debtor_id = d.id\n          )\n        ORDER BY d.paid_time ASC, d.id ASC\n        ', (start_iso, end_iso)).fetchall()
    conn.close()
    out = [dict(r) for r in rows] + [dict(r) for r in legacy]
    out.sort(key=lambda x: str(x.get('paid_time') or ''))
    return out
def count_closed_sessions_between(start_iso: str, end_iso: str) -> int:
    conn = _connect()
    row = conn.execute('\n        SELECT COUNT(*) FROM sessions\n        WHERE end_time IS NOT NULL AND end_time >= ? AND end_time < ?\n        ', (start_iso, end_iso)).fetchone()
    conn.close()
    return int(row[0] or 0)
def product_stock_report_between(start_iso: str, end_iso: str) -> List[dict[str, Any]]:
    """Tovar otchyot: narx, edi, qoldi, sotildi, summa, foyda."""
    conn = _connect()
    period = (start_iso, end_iso, start_iso, end_iso)
    sold_sql = _drink_orders_closed_or_walkin_sql("AND d.item_type IN ('drink', 'market')")
    sold_rows = conn.execute(f"\n        SELECT d.drink_name, d.volume, d.item_type,\n               COUNT(*) AS sold, SUM(d.price) AS sum_price, AVG(d.price) AS avg_price\n        {sold_sql}\n        GROUP BY d.drink_name, d.volume, d.item_type\n        ", period).fetchall()
    conn.close()
    sold_map = {}
    for r in sold_rows:
        key = (str(r['drink_name'] or ''), float(r['volume'] or 0), str(r['item_type'] or 'drink'))
        sold_map[key] = {'sold': int(r['sold'] or 0), 'sum': float(r['sum_price'] or 0), 'avg_price': float(r['avg_price'] or 0)}
    out = []
    for d in get_drink_prices():
        name = str(d.get('drink_name') or '')
        vol = float(d.get('volume') or 0)
        key = (name, vol, 'drink')
        sold_info = sold_map.pop(key, {'sold': 0, 'sum': 0.0, 'avg_price': float(d.get('price') or 0)})
        sold = int(sold_info['sold'])
        left = int(d.get('quantity') or 0)
        was = left + sold
        price = float(d.get('price') or sold_info['avg_price'] or 0)
        cost = float(d.get('cost_price') or 0)
        sm = float(sold_info['sum'] or sold * price)
        profit = sm - cost * sold
        display = f'{name} {vol:g} L' if vol else name
        out.append({'name': display, 'raw_name': name, 'volume': vol, 'kind': 'drink', 'price': price, 'was': was, 'left': left, 'sold': sold, 'sum': sm, 'profit': profit})
    for m in get_market_products():
        name = str(m.get('name') or '')
        grams = float(m.get('grams') or 0)
        key = (name, grams, 'market')
        sold_info = sold_map.pop(key, None)
        if sold_info is None:
            sold_info = sold_map.pop((name, 0.0, 'market'), {'sold': 0, 'sum': 0.0, 'avg_price': float(m.get('price') or 0)})
        sold = int(sold_info['sold'])
        left = int(m.get('quantity') or 0)
        was = left + sold
        price = float(m.get('price') or sold_info['avg_price'] or 0)
        cost = float(m.get('cost_price') or 0)
        sm = float(sold_info['sum'] or sold * price)
        profit = sm - cost * sold
        display = name
        if grams > 0 and f'{grams:g}' not in name:
                display = f'{name} {grams:g} gr'
        out.append({'name': display, 'raw_name': name, 'volume': grams, 'kind': 'market', 'price': price, 'was': was, 'left': left, 'sold': sold, 'sum': sm, 'profit': profit})
    for (name, vol, kind), info in sold_map.items():
        sold = int(info['sold'])
        sm = float(info['sum'] or 0)
        price = float(info['avg_price'] or 0)
        display = name
        if kind == 'drink' and vol:
                display = f'{name} {vol:g} L'
        out.append({'name': display, 'raw_name': name, 'volume': vol, 'kind': kind, 'price': price, 'was': sold, 'left': 0, 'sold': sold, 'sum': sm, 'profit': sm})
    out.sort(key=lambda x: str(x.get('name') or '').lower())
    return out
def expense_total_for_day(day: Optional[str]=None) -> float:
    biz_day = day or current_business_date().isoformat()
    start, end = business_day_bounds(biz_day)
    return expense_total_between(start, end)
def _setting_get(key: str, default: str='') -> str:
    conn = _connect()
    row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    if row and row['value'] is not None:
        return str(row['value'])
    else:
        return default
def _setting_set(key: str, value: str) -> None:
    conn = _connect()
    conn.execute('\n        INSERT INTO app_settings (key, value) VALUES (?, ?)\n        ON CONFLICT(key) DO UPDATE SET value = excluded.value\n        ', (key, str(value)))
    conn.commit()
    conn.close()
def get_safe_balance() -> float:
    """Ceyf balansi — kassa jabıwdagi Jawılg\'andag\'i summalar yig\'indisi."""
    try:
        return float(_setting_get('safe_balance', '0') or 0)
    except (TypeError, ValueError):
        return 0.0
def add_to_safe_balance(amount: float) -> float:
    """Ceyfga summa qo\'shish; yangi balansni qaytaradi (minglik)."""
    new_val = as_thousand(get_safe_balance() + float(amount or 0))
    _setting_set('safe_balance', f'{new_val:.2f}')
    return new_val
def get_cash_period_start() -> Optional[str]:
    """Oxirgi kassa jabıw vaqti (joriy kassa davri boshi)."""
    val = (_setting_get('cash_period_start', '') or '').strip()
    return val or None
def set_cash_period_start(iso: str) -> None:
    _setting_set('cash_period_start', (iso or '').strip())
def cash_period_bounds(day: Optional[str]=None) -> tuple[str, str]:
    """Joriy kassa davri: oxirgi jabıwdan — hozirgacha (yarim tunda uzilmasin).\n\n    Kassa yopilmaguncha kechasi 00:00 dan o\'tganda ham daromad shu smenada qoladi.\n    live_end — seans end_time bilan BIR XIL soat (trusted/network), aks holda\n    yopilgan stol daromadga tushmay qoladi.\n    """
    biz_day = day or current_business_date().isoformat()
    start, end = business_day_bounds(biz_day)
    try:
        from app.core.network_time import trusted_now_naive
        live_end = (trusted_now_naive() + timedelta(seconds=2)).isoformat(timespec='seconds')
    except Exception:
        live_end = (datetime.now() + timedelta(seconds=2)).isoformat(timespec='seconds')
    if live_end < end:
        end = live_end
    period = get_cash_period_start()
    if period:
        start = period
    return (start, end)
def cash_period_revenue(day: Optional[str]=None) -> dict[str, float]:
    """Joriy kassa davridagi tushum (Playstation + tovarlar). Buyurtma kirmaydi."""
    start, end = cash_period_bounds(day)
    report = operator_report_between(start, end)
    joy = float(report.get('joystick_total') or 0)
    goods = float(report.get('drink_total') or 0) + float(report.get('market_total') or 0)
    return {'total': float(report.get('total') or 0), 'session_total': float(report.get('session_total') or 0) + joy, 'drink_total': goods, 'joystick_total': joy, 'buyurtma_total': float(report.get('buyurtma_total') or 0), 'period_start': start, 'period_end': end}
def compute_cash_diff(total_income: float, expense_total: float, debt_total: float, debt_paid_total: float, closing_amount: float) -> tuple[float, float]:
    """Kutilgan summa va kassa farqi.\n\n    expected = tu\'sim - qa\'rejet - qarizlar + qarizin to\'legenler\n    cash_diff = jawılg\'andag\'i summa (naqd+CLICK bo\'lishi mumkin) - expected\n    """
    expected = float(total_income or 0) - float(expense_total or 0) - float(debt_total or 0) + float(debt_paid_total or 0)
    return (expected, float(closing_amount or 0) - expected)
def operator_report_for_day(day: Optional[str]=None) -> dict[str, Any]:
    """Joriy kassa davri hisoboti (oxirgi jabıwdan keyin — yangi smena)."""
    biz_day = day or current_business_date().isoformat()
    start, end = cash_period_bounds(biz_day)
    report = operator_report_between(start, end)
    report['business_day'] = biz_day
    report['debt_total'] = debtor_total_between(start, end, include_paid=True)
    report['debt_paid_total'] = debtor_paid_total_between(start, end)
    report['expense_total'] = expense_total_between(start, end)
    expected, _diff = compute_cash_diff(float(report.get('total') or 0), float(report.get('expense_total') or 0), float(report.get('debt_total') or 0), float(report.get('debt_paid_total') or 0), 0.0)
    report['expected_amount'] = expected
    return report
def close_cash_register(operator_index: int, closing_amount: float, operator_name: str='', report: Optional[dict[str, Any]]=None) -> dict[str, Any]:
    """Kassa jabıw: farqni saqlash, Jawılg\'an summani ceyfga o\'tkazish, bugungi kassani 0 qilish."""
    from app.services.shift_report import enrich_shift_report
    from app.services.telegram_notify import notify_cash_close_async
    report = dict(report or operator_report_for_day())
    closing = round_to_thousand(closing_amount)
    name = (operator_name or '').strip() or get_operator_name(int(operator_index))
    now = _session_wall_now_iso()
    if not report.get('period_end') or str(report.get('period_end')) > now:
        report['period_end'] = now
    report['closing_amount'] = closing
    if 'click_total' not in report:
        try:
            report['click_total'] = float(click_total_for_cash_period())
        except Exception:
            report['click_total'] = 0.0
    else:
        report['click_total'] = round_to_thousand(report.get('click_total'))
    report['operator_name'] = name
    report['operator_index'] = int(operator_index)
    report = enrich_shift_report(report)
    total_income = float(report.get('total') or 0)
    expense_total = float(report.get('expense_total') or 0)
    debt_total = float(report.get('debt_total') or 0)
    debt_paid = float(report.get('debt_paid_total') or 0)
    expected = float(report.get('expected_amount') or 0)
    cash_diff = float(report.get('cash_diff') or 0)
    click_total = float(report.get('click_total') or 0)
    biz_day = str(report.get('business_day') or current_business_date().isoformat())
    conn = _connect()
    try:
        conn.execute('SELECT click_total FROM cash_closes LIMIT 1')
        has_click_col = True
    except sqlite3.OperationalError:
        conn.execute('ALTER TABLE cash_closes ADD COLUMN click_total REAL NOT NULL DEFAULT 0')
        conn.commit()
        has_click_col = True
    if has_click_col:
        cur = conn.execute('\n            INSERT INTO cash_closes (\n                business_day, operator_index, operator_name, saved_time,\n                total_income, expense_total, debt_total, debt_paid_total,\n                closing_amount, expected_amount, cash_diff, period_start, period_end,\n                click_total\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ', (biz_day, int(operator_index), name, now, total_income, expense_total, debt_total, debt_paid, closing, expected, cash_diff, str(report.get('period_start') or ''), str(report.get('period_end') or now), click_total))
    else:
        cur = conn.execute('\n            INSERT INTO cash_closes (\n                business_day, operator_index, operator_name, saved_time,\n                total_income, expense_total, debt_total, debt_paid_total,\n                closing_amount, expected_amount, cash_diff, period_start, period_end\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ', (biz_day, int(operator_index), name, now, total_income, expense_total, debt_total, debt_paid, closing, expected, cash_diff, str(report.get('period_start') or ''), str(report.get('period_end') or now)))
    close_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    add_to_safe_balance(closing)
    set_cash_period_start(now)
    try:
        purge_old_expenses(30)
    except Exception:
        pass
    report['saved_time'] = now
    report_id = save_operator_report(int(operator_index), report)
    try:
        notify_cash_close_async(report)
    except Exception as e:
        logger.warning('Telegram notify: %s', e)
    return {'cash_close_id': close_id, 'report_id': report_id, 'cash_diff': cash_diff, 'expected_amount': expected, 'closing_amount': closing, 'click_total': click_total, 'safe_balance': get_safe_balance(), 'business_day': biz_day, 'operator_name': name, 'operator_index': int(operator_index), 'report': report}
def list_cash_closes(limit: int=500) -> List[dict[str, Any]]:
    """Yopilgan kassalar ro\'yxati (yangi avval)."""
    conn = _connect()
    try:
        rows = conn.execute('\n            SELECT id, business_day, operator_index, operator_name, saved_time,\n                   total_income, expense_total, debt_total, debt_paid_total,\n                   closing_amount, expected_amount, cash_diff, period_start, period_end,\n                   COALESCE(click_total, 0) AS click_total\n            FROM cash_closes\n            ORDER BY saved_time DESC, id DESC\n            LIMIT ?\n            ', (int(limit),)).fetchall()
    except sqlite3.OperationalError:
        rows = conn.execute('\n            SELECT id, business_day, operator_index, operator_name, saved_time,\n                   total_income, expense_total, debt_total, debt_paid_total,\n                   closing_amount, expected_amount, cash_diff, period_start, period_end\n            FROM cash_closes\n            ORDER BY saved_time DESC, id DESC\n            LIMIT ?\n            ', (int(limit),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def reset_stock_and_balances_keep_catalog() -> dict[str, Any]:
    """Yangi smena uchun: ombor sonlari=0, barcha summalar/tarix=0.\n\n    Saqlanadi: mahsulotlar (sotish/kelish narxi, rasm), TV sozlamalari,\n    stollar/soatlik narxlar. O\'chiriladi: seanslar, buyurtmalar, CLICK,\n    qarizlar, xarajatlar, kassa yopishlar, bronlar. Ceyf=0, kassa davri yangilanadi.\n    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute('PRAGMA foreign_keys = OFF')
    cleared = []
    for table in ['drink_orders', 'joystick_tests', 'sessions', 'debt_payment_events', 'debtors', 'bookings', 'expenses', 'cash_closes', 'operator_reports', 'click_entries']:
        try:
            cur.execute(f'DELETE FROM {table}')
            cleared.append(table)
        except sqlite3.OperationalError:
            pass
    drink_n = 0
    market_n = 0
    try:
        cur.execute('UPDATE drink_prices SET quantity = 0')
        drink_n = int(cur.rowcount or 0)
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute('UPDATE market_products SET quantity = 0')
        market_n = int(cur.rowcount or 0)
    except sqlite3.OperationalError:
        pass
    cur.execute('INSERT INTO app_settings (key, value) VALUES (\'safe_balance\', \'0\') ON CONFLICT(key) DO UPDATE SET value = excluded.value')
    try:
        from app.core.network_time import trusted_now_naive
        now = trusted_now_naive().isoformat(timespec='seconds')
    except Exception:
        now = datetime.now().isoformat(timespec='seconds')
    cur.execute('INSERT INTO app_settings (key, value) VALUES (\'cash_period_start\', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (now,))
    try:
        cur.execute('DELETE FROM sqlite_sequence')
    except sqlite3.OperationalError:
        pass
    cur.execute('PRAGMA foreign_keys = ON')
    conn.commit()
    conn.close()
    return {'cleared_tables': cleared, 'drink_qty_zeroed': drink_n, 'market_qty_zeroed': market_n, 'cash_period_start': now, 'safe_balance': 0.0}
def wipe_accounting_keep_tv() -> dict[str, Any]:
    """Hisob-kitobni tozalash: faqat tv_settings (TV sozlamalari) saqlanadi.\n\n    Seanslar, buyurtmalar, qarizlar, kassa, CLICK, ombor, bronlar — hammasi o\'chadi.\n    Har bir stol uchun default station_prices qayta yaratiladi (dastur ishlashi uchun).\n    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute('PRAGMA foreign_keys = OFF')
    tv_rows = cur.execute('SELECT station_id, tv_ip, tv_mac, brand, volume, hdmi_input FROM tv_settings').fetchall()
    cleared = []
    for table in ['drink_orders', 'joystick_tests', 'sessions', 'debt_payment_events', 'debtors', 'bookings', 'expenses', 'cash_closes', 'operator_reports', 'click_entries', 'station_price_slots', 'station_prices', 'drink_prices', 'market_products']:
        try:
            cur.execute(f'DELETE FROM {table}')
            cleared.append(table)
        except sqlite3.OperationalError:
            pass
    cur.execute('INSERT INTO app_settings (key, value) VALUES (\'safe_balance\', \'0\') ON CONFLICT(key) DO UPDATE SET value = excluded.value')
    now = datetime.now().isoformat(timespec='seconds')
    cur.execute('INSERT INTO app_settings (key, value) VALUES (\'cash_period_start\', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (now,))
    cur.execute('DELETE FROM prices')
    cur.execute('INSERT INTO prices (id, hourly_rate) VALUES (1, ?)', (20000.0,))
    for r in tv_rows:
        sid = str(r['station_id'])
        cur.execute('\n            INSERT OR IGNORE INTO station_prices (station_id, hourly_rate, display_name)\n            VALUES (?, ?, ?)\n            ', (sid, 20000.0, sid))
    try:
        cur.execute('DELETE FROM sqlite_sequence')
    except sqlite3.OperationalError:
        pass
    cur.execute('PRAGMA foreign_keys = ON')
    conn.commit()
    conn.close()
    return {'tv_stations': len(tv_rows), 'cleared_tables': cleared, 'cash_period_start': now, 'safe_balance': 0.0}
def save_operator_report(operator_index: int, report: dict[str, Any]) -> int:
    """Operator hisobotini saqlaydi (Adminga topshirish uchun). Yangi id qaytaradi."""
    import json as _json
    conn = _connect()
    now = datetime.now().isoformat(timespec='seconds')
    details = _json.dumps({
        'drinks': report.get('drinks', []),
        'market': report.get('market', []),
        'expenses': report.get('expenses', []),
        'debtors': report.get('debtors', []),
        'debt_payments': report.get('debt_payments', []),
        'products': report.get('products', []),
        'debt_total': float(report.get('debt_total', 0)),
        'debt_paid_total': float(report.get('debt_paid_total', 0)),
        'expense_total': float(report.get('expense_total', 0)),
        'goods_total': float(report.get('goods_total', 0)),
        'closing_amount': float(report.get('closing_amount', 0)),
        'expected_amount': float(report.get('expected_amount', 0)),
        'cash_diff': float(report.get('cash_diff', 0)),
        'operator_name': str(report.get('operator_name') or ''),
        'client_count': int(report.get('client_count') or 0),
        'avg_payment': float(report.get('avg_payment') or 0),
        'goods_profit': float(report.get('goods_profit') or 0),
        'net_profit': float(report.get('net_profit') or 0),
        'session_total': float(report.get('session_total') or 0),
        'joystick_total': float(report.get('joystick_total') or 0),
        'total': float(report.get('total') or 0),
        'summary_text': str(report.get('summary_text') or ''),
        'details_text': str(report.get('details_text') or ''),
    })
    cur = conn.execute('\n        INSERT INTO operator_reports (\n            operator_index, business_day, saved_time, period_start, period_end,\n            total_revenue, session_revenue, drink_revenue, market_revenue,\n            joystick_revenue, details_json\n        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ', (int(operator_index), str(report.get('business_day', current_business_date().isoformat())), now, str(report.get('period_start', '')), str(report.get('period_end', '')), float(report.get('total', 0)), float(report.get('session_total', 0)), float(report.get('drink_total', 0)), float(report.get('market_total', 0)), float(report.get('joystick_total', 0)), details))
    new_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return new_id
def get_operator_name(operator_index: int) -> str:
    """Operator nomi (masalan \'Amir\'). Belgilanmagan bo\'lsa \'{n}-operator\'."""
    conn = _connect()
    row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (f'operator_name_{int(operator_index)}',)).fetchone()
    conn.close()
    if row and str(row['value']).strip():
        return str(row['value']).strip()
    else:
        return f'{int(operator_index)}-operator'
def set_operator_name(operator_index: int, name: str) -> None:
    """Operator nomini saqlash."""
    value = (name or '').strip()
    conn = _connect()
    conn.execute('\n        INSERT INTO app_settings (key, value) VALUES (?, ?)\n        ON CONFLICT(key) DO UPDATE SET value = excluded.value\n        ', (f'operator_name_{int(operator_index)}', value))
    conn.commit()
    conn.close()
def delete_operator_report(report_id: int) -> None:
    """Bitta operator hisobotini o\'chirish."""
    conn = _connect()
    conn.execute('DELETE FROM operator_reports WHERE id = ?', (int(report_id),))
    conn.commit()
    conn.close()
def get_operator_reports(operator_index: int) -> List[dict[str, Any]]:
    """Bitta operator topshirgan hisobotlar ro\'yxati (yangi avval)."""
    import json as _json
    conn = _connect()
    rows = conn.execute('\n        SELECT * FROM operator_reports\n        WHERE operator_index = ?\n        ORDER BY saved_time DESC\n        ', (int(operator_index),)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            parsed = _json.loads(d.get('details_json') or '{}')
        except Exception:
            parsed = {}
        d['drinks'] = parsed.get('drinks', [])
        d['market'] = parsed.get('market', [])
        d['expenses'] = parsed.get('expenses', [])
        d['debtors'] = parsed.get('debtors', [])
        d['debt_payments'] = parsed.get('debt_payments', [])
        d['products'] = parsed.get('products', [])
        for key in ['debt_total', 'debt_paid_total', 'expense_total', 'goods_total', 'closing_amount', 'expected_amount', 'cash_diff', 'operator_name', 'client_count', 'avg_payment', 'goods_profit', 'net_profit', 'session_total', 'joystick_total', 'total', 'summary_text', 'details_text']:
            if key in parsed:
                d[key] = parsed[key]
        if 'session_total' not in d:
            d['session_total'] = float(d.get('session_revenue') or 0)
        if 'total' not in d or not d.get('total'):
            d['total'] = float(d.get('total_revenue') or 0)
        out.append(d)
    return out