"""\nControl PS — Online litsenziya serveri.\nIshga tushirish:\n  python -m app.auth.license_server\n  yoki license_server/start_server.bat\nAdmin panel: http://KOMPUTER_IP:5050/admin\n"""
from __future__ import annotations
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request, Response
from app.core.runtime import app_dir
APP_DIR = app_dir() / 'license_server'
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APP_DIR / 'config.json'
DB_PATH = APP_DIR / 'license_server.db'
_EXAMPLE_CONFIG = Path(__file__).resolve().parent / 'config.example.json'
app = Flask(__name__)
def load_config() -> dict:
    if CONFIG_PATH.is_file():
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    example = _EXAMPLE_CONFIG if _EXAMPLE_CONFIG.is_file() else APP_DIR / 'config.example.json'
    if example.is_file():
        with open(example, encoding='utf-8') as f:
            cfg = json.load(f)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f'config.json yaratildi: {CONFIG_PATH}')
        print('admin_token va client_api_key ni o\'zgartiring!')
        return cfg
    else:
        return {'host': '0.0.0.0', 'port': 5050, 'admin_token': 'admin123', 'client_api_key': 'client123', 'auto_block_on_tamper': True}
CFG = load_config()
if CFG.get('db_path'):
    p = Path(CFG['db_path'])
    DB_PATH = p if p.is_absolute() else APP_DIR / p
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn
def init_db() -> None:
    conn = _connect()
    conn.executescript('\n        CREATE TABLE IF NOT EXISTS clients (\n            hwid TEXT PRIMARY KEY,\n            client_name TEXT NOT NULL DEFAULT \'\',\n            license_type TEXT NOT NULL DEFAULT \'MONTHLY\',\n            expiry TEXT,\n            blocked INTEGER NOT NULL DEFAULT 0,\n            block_reason TEXT NOT NULL DEFAULT \'\',\n            tamper_count INTEGER NOT NULL DEFAULT 0,\n            last_seen TEXT,\n            created_at TEXT NOT NULL\n        );\n        CREATE TABLE IF NOT EXISTS tamper_log (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            hwid TEXT NOT NULL,\n            event TEXT NOT NULL,\n            detail TEXT NOT NULL DEFAULT \'\',\n            ip TEXT NOT NULL DEFAULT \'\',\n            created_at TEXT NOT NULL\n        );\n        ')
    conn.commit()
    conn.close()
def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')
def _days_left(expiry_str: str | None) -> int | None:
    if not expiry_str:
        return
    else:
        try:
            exp = date.fromisoformat(expiry_str)
            return (exp - date.today()).days
        except ValueError:
            return None
def _check_admin() -> bool:
    token = request.headers.get('X-Admin-Token') or request.args.get('token', '')
    return token == CFG.get('admin_token', '')
def _check_client_api() -> bool:
    key = request.headers.get('X-API-Key', '')
    return key == CFG.get('client_api_key', '')
def _client_row(hwid: str) -> sqlite3.Row | None:
    conn = _connect()
    row = conn.execute('SELECT * FROM clients WHERE hwid = ?', (hwid.upper(),)).fetchone()
    conn.close()
    return row
def _log_tamper(hwid: str, event: str, detail: str, ip: str) -> None:
    conn = _connect()
    conn.execute('INSERT INTO tamper_log (hwid, event, detail, ip, created_at) VALUES (?, ?, ?, ?, ?)', (hwid.upper(), event, detail[:500], ip, _now()))
    conn.execute('\n        UPDATE clients SET tamper_count = tamper_count + 1, last_seen = ?\n        WHERE hwid = ?\n        ', (_now(), hwid.upper()))
    if CFG.get('auto_block_on_tamper', True):
        conn.execute('\n            UPDATE clients SET blocked = 1,\n            block_reason = ?\n            WHERE hwid = ?\n            ', (f'Buzish urinishi: {detail[:200]}', hwid.upper()))
    conn.commit()
    conn.close()
@app.route('/api/v1/check', methods=['POST'])
def api_check():
    if not _check_client_api():
        return (jsonify({'allowed': False, 'message': 'API kalit noto\'g\'ri'}), 403)
    else:
        data = request.get_json(silent=True) or {}
        hwid = str(data.get('hwid', '')).strip().upper()
        event = str(data.get('event', 'startup')).strip().lower()
        detail = str(data.get('detail', '')).strip()
        ip = request.remote_addr or ''
        if not hwid:
            return (jsonify({'allowed': False, 'message': 'HWID yo\'q'}), 400)
        else:
            if event == 'tamper':
                _ensure_client(hwid)
                _log_tamper(hwid, event, detail or 'noma\'lum', ip)
                row = _client_row(hwid)
                return jsonify({'allowed': False, 'blocked': True, 'message': 'Buzish aniqlandi. Dastur bloklandi. Dasturchi bilan bog\'laning.', 'tamper_count': int(row['tamper_count']) if row else 1})
            else:
                row = _client_row(hwid)
                if row is None:
                    _ensure_client(hwid)
                    row = _client_row(hwid)
                conn = _connect()
                conn.execute('UPDATE clients SET last_seen = ? WHERE hwid = ?', (_now(), hwid))
                conn.commit()
                conn.close()
                if int(row['blocked'] or 0):
                    return jsonify({'allowed': False, 'blocked': True, 'days_left': _days_left(row['expiry']), 'client_name': row['client_name'], 'message': row['block_reason'] or 'Server tomonidan bloklangan'})
                else:
                    days = _days_left(row['expiry'])
                    if row['license_type'] == 'MONTHLY' and days is not None and (days < 0):
                        return jsonify({'allowed': False, 'blocked': False, 'days_left': days, 'client_name': row['client_name'], 'message': 'Litsenziya muddati tugagan'})
                    else:
                        return jsonify({'allowed': True, 'blocked': False, 'days_left': days, 'client_name': row['client_name'], 'message': 'OK'})
def _ensure_client(hwid: str) -> None:
    conn = _connect()
    conn.execute('\n        INSERT OR IGNORE INTO clients (hwid, client_name, license_type, created_at)\n        VALUES (?, ?, \'MONTHLY\', ?)\n        ', (hwid.upper(), hwid.upper(), _now()))
    conn.commit()
    conn.close()
@app.route('/api/v1/register', methods=['POST'])
def api_register():
    if not _check_admin():
        return (jsonify({'ok': False, 'message': 'Admin token noto\'g\'ri'}), 403)
    else:
        data = request.get_json(silent=True) or {}
        hwid = str(data.get('hwid', '')).strip().upper()
        name = str(data.get('client_name', '')).strip() or hwid
        lic_type = 'PERMANENT' if str(data.get('type', '1')) == '2' else 'MONTHLY'
        expiry = data.get('expiry')
        if not hwid:
            return (jsonify({'ok': False, 'message': 'HWID kerak'}), 400)
        else:
            if lic_type == 'MONTHLY' and (not expiry):
                    d = date.today()
                    m = d.month + 1
                    y = d.year
                    if m > 12:
                        m, y = (1, y + 1)
                    expiry = date(y, m, 10).isoformat()
            conn = _connect()
            conn.execute('\n        INSERT INTO clients (hwid, client_name, license_type, expiry, blocked, block_reason,\n                             tamper_count, last_seen, created_at)\n        VALUES (?, ?, ?, ?, 0, \'\', 0, ?, ?)\n        ON CONFLICT(hwid) DO UPDATE SET\n            client_name = excluded.client_name,\n            license_type = excluded.license_type,\n            expiry = excluded.expiry,\n            blocked = 0,\n            block_reason = \'\'\n        ', (hwid, name, lic_type, expiry, _now(), _now()))
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'hwid': hwid, 'expiry': expiry})
@app.route('/api/admin/clients')
def admin_clients():
    if not _check_admin():
        return (jsonify({'ok': False}), 403)
    else:
        conn = _connect()
        rows = conn.execute('SELECT * FROM clients ORDER BY blocked DESC, last_seen DESC').fetchall()
        logs = conn.execute('SELECT * FROM tamper_log ORDER BY id DESC LIMIT 50').fetchall()
        conn.close()
        clients = []
        for r in rows:
            clients.append({'hwid': r['hwid'], 'client_name': r['client_name'], 'license_type': r['license_type'], 'expiry': r['expiry'], 'days_left': _days_left(r['expiry']), 'blocked': bool(r['blocked']), 'block_reason': r['block_reason'], 'tamper_count': r['tamper_count'], 'last_seen': r['last_seen']})
        tamper = [dict(x) for x in logs]
        return jsonify({'ok': True, 'clients': clients, 'tamper_log': tamper})
@app.route('/api/admin/block', methods=['POST'])
def admin_block():
    if not _check_admin():
        return (jsonify({'ok': False}), 403)
    else:
        data = request.get_json(silent=True) or {}
        hwid = str(data.get('hwid', '')).strip().upper()
        reason = str(data.get('reason', 'Admin blokladi')).strip()
        conn = _connect()
        conn.execute('UPDATE clients SET blocked = 1, block_reason = ? WHERE hwid = ?', (reason, hwid))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
@app.route('/api/admin/unblock', methods=['POST'])
def admin_unblock():
    if not _check_admin():
        return (jsonify({'ok': False}), 403)
    else:
        data = request.get_json(silent=True) or {}
        hwid = str(data.get('hwid', '')).strip().upper()
        conn = _connect()
        conn.execute('UPDATE clients SET blocked = 0, block_reason = \'\', tamper_count = 0 WHERE hwid = ?', (hwid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
ADMIN_HTML = '<!DOCTYPE html>\n<html lang=\"uz\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Control PS — Litsenziya</title>\n<style>\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;padding:12px}\nh1{font-size:1.3rem;color:#38bdf8;margin-bottom:12px;text-align:center}\n.card{background:#1e293b;border-radius:12px;padding:14px;margin-bottom:12px;border:1px solid #334155}\ninput,button{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;font-size:15px}\nbutton{background:#0284c7;border:none;font-weight:bold;cursor:pointer}\nbutton.red{background:#dc2626}\nbutton.green{background:#16a34a}\n.badge{display:inline-block;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:bold}\n.ok{background:#166534}.bad{background:#991b1b}.warn{background:#854d0e}\n.client{border-bottom:1px solid #334155;padding:10px 0}\n.client:last-child{border:none}\n.small{font-size:12px;color:#94a3b8}\n.row{display:flex;gap:8px}.row button{flex:1}\n#login{max-width:400px;margin:40px auto}\n.hidden{display:none}\n</style>\n</head>\n<body>\n<div id=\"login\" class=\"card\">\n  <h1>Control PS Admin</h1>\n  <input id=\"tokenIn\" type=\"password\" placeholder=\"Admin token\">\n  <button onclick=\"saveToken()\">Kirish</button>\n</div>\n<div id=\"app\" class=\"hidden\">\n  <h1>Litsenziyalar</h1>\n  <div class=\"card\">\n    <button onclick=\"load()\">Yangilash</button>\n  </div>\n  <div class=\"card\"><div id=\"list\"></div></div>\n  <div class=\"card\"><h3 style=\"margin-bottom:8px\">Buzish urinishlari</h3><div id=\"logs\"></div></div>\n</div>\n<script>\nconst TKEY=\'cps_admin_token\';\nfunction tok(){return localStorage.getItem(TKEY)||\'\'}\nfunction saveToken(){\n  localStorage.setItem(TKEY,document.getElementById(\'tokenIn\').value.trim());\n  boot();\n}\nfunction boot(){\n  if(location.hash.indexOf(\'token=\')>-1){\n    const t=decodeURIComponent(location.hash.split(\'token=\')[1]);\n    localStorage.setItem(TKEY,t);\n    history.replaceState(null,\'\',location.pathname);\n  }\n  if(!tok()){document.getElementById(\'login\').classList.remove(\'hidden\');document.getElementById(\'app\').classList.add(\'hidden\');return}\n  document.getElementById(\'login\').classList.add(\'hidden\');\n  document.getElementById(\'app\').classList.remove(\'hidden\');\n  load();\n}\nasync function load(){\n  const r=await fetch(\'/api/admin/clients?token=\'+encodeURIComponent(tok()));\n  if(!r.ok){alert(\'Token xato\');localStorage.removeItem(TKEY);boot();return}\n  const d=await r.json();\n  const el=document.getElementById(\'list\');\n  el.innerHTML=\'\';\n  d.clients.forEach(c=>{\n    const st=c.blocked?\'<span class=\"badge bad\">BLOK</span>\':\n      (c.days_left!=null&&c.days_left<0?\'<span class=\"badge warn\">MUDDAT</span>\':\'<span class=\"badge ok\">OK</span>\');\n    const days=c.days_left!=null?c.days_left+\' kun\':\'doimiy\';\n    el.innerHTML+=`<div class=\"client\">\n      <b>${c.client_name}</b> ${st}<br>\n      <span class=\"small\">${c.hwid}</span><br>\n      Qoldiq: <b>${days}</b> | Buzish: ${c.tamper_count}<br>\n      <span class=\"small\">Oxirgi: ${c.last_seen||\'-\'}</span>\n      <div class=\"row\">\n        ${c.blocked?`<button class=\"green\" onclick=\"unblock(\'${c.hwid}\')\">Ochish</button>`:`<button class=\"red\" onclick=\"block(\'${c.hwid}\')\">Blok</button>`}\n      </div>\n    </div>`;\n  });\n  const lg=document.getElementById(\'logs\');\n  lg.innerHTML=\'\';\n  d.tamper_log.forEach(t=>{\n    lg.innerHTML+=`<div class=\"small\" style=\"padding:6px 0;border-bottom:1px solid #334155\">\n      <b>${t.hwid}</b> — ${t.detail}<br>${t.created_at} (${t.ip})\n    </div>`;\n  });\n}\nasync function block(hwid){\n  await fetch(\'/api/admin/block?token=\'+encodeURIComponent(tok()),{method:\'POST\',headers:{\'Content-Type\':\'application/json\',\'X-Admin-Token\':tok()},body:JSON.stringify({hwid,reason:\'Admin blokladi\'})});\n  load();\n}\nasync function unblock(hwid){\n  await fetch(\'/api/admin/unblock?token=\'+encodeURIComponent(tok()),{method:\'POST\',headers:{\'Content-Type\':\'application/json\',\'X-Admin-Token\':tok()},body:JSON.stringify({hwid})});\n  load();\n}\nboot();\nsetInterval(load,30000);\n</script>\n</body>\n</html>'
@app.route('/admin')
def admin_page():
    return Response(ADMIN_HTML, mimetype='text/html; charset=utf-8')
if __name__ == '__main__':
    init_db()
    host = CFG.get('host', '0.0.0.0')
    port = int(CFG.get('port', 5050))
    print('==================================================')
    print('  Control PS License Server')
    print(f'  Admin: http://127.0.0.1:{port}/admin')
    print(f'  Telefon: http://KOMPUTER_IP:{port}/admin')
    print('==================================================')
    app.run(host=host, port=port, debug=False, threaded=True)