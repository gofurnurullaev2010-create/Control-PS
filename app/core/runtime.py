"""Control PS — umumiy yo\'llar, log va konfiguratsiya yuklash."""
from __future__ import annotations
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional
_LOG_CONFIGURED = False
def app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parents[2]
def project_tools_dir() -> Path:
    """Lokal ares-cli / sdb (dist/ dan ishlaganda ../tools)."""
    base = app_dir()
    for candidate in [base / 'tools', base.parent / 'tools']:
        if (candidate / 'ares-cli' / 'node_modules').is_dir():
            return candidate
    return base / 'tools'
def ensure_tv_tools_path() -> None:
    """ares-cli npm global o\'rniga loyiha tools/ dan ishlashi uchun PATH."""
    tools_bin = project_tools_dir() / 'ares-cli' / 'node_modules' / '.bin'
    if not tools_bin.is_dir():
        return
    else:
        bin_str = str(tools_bin)
        path = os.environ.get('PATH', '')
        if bin_str.casefold() not in {p.casefold() for p in path.split(os.pathsep) if p}:
            os.environ['PATH'] = bin_str + os.pathsep + path
def bundle_path(filename: str) -> Optional[Path]:
    """Exe yonidagi yoki PyInstaller ichidagi resurs fayl."""
    name = (filename or '').strip().lstrip('/\\')
    if not name:
        return
    base = app_dir()
    for candidate in [base / name, base / 'dist' / name]:
        if candidate.is_file():
            return candidate
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        embedded = Path(meipass) / name
        if embedded.is_file():
            return embedded
    return None
def setup_logging() -> None:
    """Bitta marta: fayl + konsol log (mijozda nosozlikni topish uchun)."""
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return
    else:
        _LOG_CONFIGURED = True
        log_path = app_dir() / 'control_ps.log'
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        try:
            fh = RotatingFileHandler(log_path, maxBytes=5242880, backupCount=5, encoding='utf-8')
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError:
            pass
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
        _enable_faulthandler(log_path)
def _enable_faulthandler(log_path: 'Path') -> None:
    """Native (C/Qt darajasidagi) qulashlarni faylga yozish.\n\n    Dastur jim yopilib qolsa, sababi shu faylda traceback bo\'lib qoladi.\n    """
    global _CRASH_FILE
    import faulthandler
    try:
        crash_path = log_path.parent / 'crash_native.log'
        _CRASH_FILE = open(crash_path, 'a', encoding='utf-8')
        faulthandler.enable(file=_CRASH_FILE, all_threads=True)
    except Exception as e:
        logging.getLogger(__name__).debug('faulthandler yoqilmadi: %s', e)
_CRASH_FILE = None
def load_json_config(name: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dastur papkasidagi JSON (masalan tv_config.json)."""
    defaults = dict(defaults or {})
    path = app_dir() / name
    if not path.is_file():
        return defaults
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {**defaults, **data}
        return defaults
    except (OSError, json.JSONDecodeError, TypeError) as e:
        logging.getLogger(__name__).warning("%s o'qilmadi: %s", name, e)
        return defaults


def save_json_config(name: str, data: Dict[str, Any]) -> bool:
    """JSON konfiguratsiyani dastur papkasiga yozish."""
    path = app_dir() / name
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except OSError as e:
        logging.getLogger(__name__).warning('%s yozilmadi: %s', name, e)
        return False
    else:
        return True