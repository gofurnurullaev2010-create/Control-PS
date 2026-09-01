"""\nLitsenziya yaratuvchi (FAQAT dasturchi — mijozga bermang).\nImzoli license.key — EXPIRY o\'zgartirib bo\'lmaydi.\n\n  python keygen.py HWID 1     — oylik\n  python keygen.py HWID 2     — doimiy\n  python -m app.auth.tools.keygen HWID 1\n"""
from __future__ import annotations
import sys
from datetime import date, timedelta
from pathlib import Path
from app.auth.license_manager import build_license_content, get_next_monthly_expiry, write_license_file
from app.auth import license_registry
def _parse_expiry(arg: str) -> date:
    arg = arg.strip()
    if arg.startswith('+') and arg[1:].isdigit():
        days = int(arg[1:])
        return date.today() + timedelta(days=days)
    else:
        return date.fromisoformat(arg)
def _turi_oylik(turi: str) -> bool | None:
    if turi == '1':
        return True
    if turi == '2':
        return False
    return None


def main() -> None:
    print('==============================================')
    print('  CONTROL PS — IMZOLI LITSENZIYA')
    print('  1=oylik   2=doimiy')
    print('==============================================')
    args = sys.argv[1:]
    expiry_date = None
    out_dir = Path.cwd()
    if '--expiry' in args:
        i = args.index('--expiry')
        if i + 1 >= len(args):
            print('--expiry dan keyin sana kerak (YYYY-MM-DD yoki +365)')
            sys.exit(1)
        expiry_date = _parse_expiry(args[i + 1])
        args = args[:i] + args[i + 2:]
    hwid = ''
    turi_arg = ''
    if args:
        hwid = args[0].strip()
        if len(args) > 1 and args[1] in ['1', '2']:
            turi_arg = args[1]
            if len(args) > 2:
                out_dir = Path(args[2]).resolve()
        else:
            if len(args) > 1:
                out_dir = Path(args[1]).resolve()
    else:
        hwid = input('Mijoz HWID: ').strip()
    if not hwid:
        print('HWID bo\'sh.')
        sys.exit(1)
    oylik = _turi_oylik(turi_arg) if turi_arg else None
    if oylik is None and expiry_date is None:
        print()
        print('  1 — Oylik (keyingi oy 10-sanagacha)')
        print('  2 — Doimiy (abadiy)')
        while True:
            turi_arg = input('1 yoki 2: ').strip()
            oylik = _turi_oylik(turi_arg)
            if oylik is not None:
                break
            print('Faqat 1 yoki 2!')
    if expiry_date is None:
        expiry_date = get_next_monthly_expiry() if oylik else None
    out = out_dir / 'license.key'
    write_license_file(hwid, expiry_date, out)
    lic_type = 'PERMANENT' if not expiry_date else 'MONTHLY'
    license_registry.save_client(hwid, lic_type, expiry_date, out_dir)
    print(f'\nOK: {out}')
    print(build_license_content(hwid, expiry_date))
    if expiry_date:
        print('Turi: OYLIK (imzoli)')
    else:
        print('Turi: DOIMIY (imzoli)')
    print()
    print(license_registry.format_roster(out_dir))
if __name__ == '__main__':
    main()