import hashlib
import hmac
import sys
from datetime import date
from pathlib import Path
HWID = ''
TURI = ''
SAQLASH_PAPKA = ''
SALT = 'CONTROL_PS_SECRET_SALT_2026_BY_ADMIN!@#'
SIGN = 'CONTROL_PS_HMAC_SIGN_2026!@#'
def skript_papka() -> Path:
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
    try:
        here = Path(__file__).resolve().parents[2]
        if here.is_dir():
            return here
    except (NameError, OSError, IndexError):
        pass
    dl = Path('/storage/emulated/0/Download')
    if dl.is_dir():
        return dl.resolve()
    return Path.cwd().resolve()
def run():
    hwid = HWID.strip().upper()
    turi = TURI.strip()
    if not hwid:
        print('XATO: HWID yozilmagan!')
        print('Masalan: HWID = \"A1B2-C3D4-E5F6-7890\"')
        return
    else:
        if turi not in ['1', '2']:
            print('XATO: TURI 1 yoki 2 bolishi kerak!')
            print('1 = oylik,  2 = doimiy')
            return
        else:
            expiry = None
            if turi == '1':
                d = date.today()
                m = d.month + 1
                y = d.year
                if m > 12:
                    m = 1
                    y += 1
                expiry = date(y, m, 10)
            key = hashlib.sha256((hwid + SALT).encode()).hexdigest()[:32].upper()
            exp_txt = expiry.isoformat() if expiry else 'PERMANENT'
            sign = hmac.new(SIGN.encode(), f'{hwid}|{exp_txt}'.encode(), hashlib.sha256).hexdigest().upper()
            lines = [f'HWID={hwid}', f'KEY={key}', f"TYPE={('MONTHLY' if expiry else 'PERMANENT')}"]
            if expiry:
                lines.append(f'EXPIRY={expiry.isoformat()}')
            lines.append(f'SIGN={sign}')
            text = '\n'.join(lines) + '\n'
            out = skript_papka() / 'license.key'
            out.write_text(text, encoding='utf-8')
            out = out.resolve()
            print('========================================')
            print('TAYYOR!')
            print('========================================')
            print(text)
            print('Fayl:', out)
            if expiry:
                print('Oylik - blok:', expiry.strftime('%d.%m.%Y'))
            else:
                print('Doimiy')
run()