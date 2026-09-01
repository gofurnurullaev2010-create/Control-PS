"""\nTelefon (Pydroid) — litsenziya + mijozlar ro\'yxati.\n\nREJIM = \"license\"  → license.key yaratish\nREJIM = \"list\"     → barcha mijozlar (soni, qolgan kun)\n\nLicense yaratganda avtomatik mijozlar.json ga yoziladi.\n\n  python -m app.auth.tools.keygen_mobile\n  yoki\n  python keygen_mobile.py\n"""
from __future__ import annotations
import hashlib
import hmac
import json
import traceback
from datetime import date, datetime
from pathlib import Path
REJIM = 'license'
HWID_KIRITISH = ''
TURI_KIRITISH = ''
MIJOZ_NOMI = ''
SAQLASH_PAPKA = ''
_SALT = 'CONTROL_PS_SECRET_SALT_2026_BY_ADMIN!@#'
_SIGN_SECRET = 'CONTROL_PS_HMAC_SIGN_2026!@#'
MONTHLY_EXPIRY_DAY = 10
REGISTRY_NAME = 'mijozlar.json'
def _base_dir() -> Path:
    if SAQLASH_PAPKA.strip():
        p = Path(SAQLASH_PAPKA.strip())
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()
    else:
        try:
            from app.core.runtime import app_dir
            return app_dir()
        except Exception:
            pass
        dl = Path('/storage/emulated/0/Download')
        if dl.is_dir():
            return dl.resolve()
        else:
            return Path.cwd().resolve()
def _next_monthly_expiry(today: date | None=None) -> date:
    today = today or date.today()
    m = today.month + 1
    y = today.year
    if m > 12:
        m = 1
        y += 1
    return date(y, m, MONTHLY_EXPIRY_DAY)
def _build_license(hwid: str, expiry: date | None) -> str:
    hwid = hwid.strip().upper()
    key = hashlib.sha256((hwid + _SALT).encode()).hexdigest()[:32].upper()
    exp_txt = expiry.isoformat() if expiry else 'PERMANENT'
    sign = hmac.new(_SIGN_SECRET.encode(), f'{hwid}|{exp_txt}'.encode(), hashlib.sha256).hexdigest().upper()
    lines = [f'HWID={hwid}', f'KEY={key}', f"TYPE={('MONTHLY' if expiry else 'PERMANENT')}"]
    if expiry:
        lines.append(f'EXPIRY={expiry.isoformat()}')
    lines.append(f'SIGN={sign}')
    return '\n'.join(lines) + '\n'
def _registry_path(base: Path) -> Path:
    return base / REGISTRY_NAME
def _load_registry(base: Path) -> list[dict]:
    path = _registry_path(base)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get('clients'), list):
            return data['clients']
    except Exception:
        pass
    return []
def _save_registry(base: Path, rows: list[dict]) -> None:
    path = _registry_path(base)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def _save_client(base: Path, hwid: str, lic_type: str, expiry: date | None, name: str='') -> None:
    rows = _load_registry(base)
    entry = {'hwid': hwid.strip().upper(), 'type': lic_type, 'expiry': expiry.isoformat() if expiry else None, 'name': name.strip(), 'updated': datetime.now().isoformat(timespec='seconds')}
    found = False
    for i, row in enumerate(rows):
        if str(row.get('hwid', '')).upper() == entry['hwid']:
            rows[i] = {**row, **entry}
            found = True
            break
    if not found:
        rows.append(entry)
    _save_registry(base, rows)
def _format_roster(base: Path) -> str:
    rows = _load_registry(base)
    if not rows:
        return 'Mijozlar yo\'q.'
    else:
        lines = [f'Jami mijozlar: {len(rows)}', '----------------------------------------']
        today = date.today()
        for row in rows:
            hwid = row.get('hwid', '?')
            name = row.get('name') or ''
            lic_type = row.get('type', '?')
            exp = row.get('expiry')
            left = ''
            if exp:
                try:
                    days = (date.fromisoformat(str(exp)) - today).days
                    left = f' | qoldi: {days} kun'
                except ValueError:
                    left = f' | EXPIRY={exp}'
            else:
                left = ' | doimiy'
            title = f'{name} ' if name else ''
            lines.append(f'{title}{hwid} [{lic_type}]{left}')
        return '\n'.join(lines)
def run_license() -> None:
    hwid = HWID_KIRITISH.strip().upper()
    turi = TURI_KIRITISH.strip()
    if not hwid:
        print('XATO: HWID_KIRITISH yozilmagan!')
        return
    else:
        if turi not in ['1', '2']:
            print('XATO: TURI_KIRITISH 1 yoki 2 bo\'lishi kerak!')
            return
        else:
            expiry = _next_monthly_expiry() if turi == '1' else None
            text = _build_license(hwid, expiry)
            base = _base_dir()
            out = base / 'license.key'
            out.write_text(text, encoding='utf-8')
            lic_type = 'MONTHLY' if expiry else 'PERMANENT'
            _save_client(base, hwid, lic_type, expiry, MIJOZ_NOMI)
            print('========================================')
            print('TAYYOR!')
            print('========================================')
            print(text)
            print('Fayl:', out.resolve())
            print()
            print(_format_roster(base))
def run_list() -> None:
    print(_format_roster(_base_dir()))
def main() -> None:
    try:
        mode = (REJIM or 'license').strip().lower()
        if mode == 'list':
            run_list()
        else:
            run_license()
    except Exception:
        traceback.print_exc()
if __name__ == '__main__':
    main()