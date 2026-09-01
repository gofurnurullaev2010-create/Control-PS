"""\nControl PS — Professional Club Management System\n\nIshga tushirish:\n  python main.py              — modular shell (standart)\n  python -m app.main          — xuddi shu\n  set CONTROL_PS_LEGACY=1 && python main.py  — eski shell\n\nLegacy shell: app.ui.legacy_main_window (ui_manager.MainWindow)\n"""
from __future__ import annotations
import os
import sys
def main() -> None:
    if os.environ.get('CONTROL_PS_LEGACY', '').strip() in ['1', 'true', 'yes']:
        from app.main_legacy import main as legacy_main
        legacy_main()
    else:
        from app.main import main as modular_main
        modular_main()
if __name__ == '__main__':
    main()