# -*- coding: utf-8 -*-
"""ControlPS_v*.exe yig'ish (PyInstaller) — v197 bilan bir xil onefile windowed."""
from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

datas = [
    (str(ROOT / "lock.html"), "."),
    (str(ROOT / "ps_bg.jpg"), "."),
    (str(ROOT / "ps_logo.png"), "."),
    (str(ROOT / "lock_screen_bg.png"), "."),
    (str(ROOT / "raptor_logo.png"), "."),
    (str(ROOT / "transfer_icon.png"), "."),
    (str(ROOT / "controlps-lock.apk"), "."),
    (str(ROOT / "controlps-lock.ipk"), "."),
    (str(ROOT / "controlps-lock.wgt"), "."),
]
for name in [
    "zakaz_n1.mp3", "zakaz_n1.wav",
    "zakaz_n2.mp3", "zakaz_n2.wav",
    "zakaz_n3.mp3", "zakaz_n3.wav",
    "zakaz_n4.mp3", "zakaz_n4.wav",
    "zakaz_n5.mp3", "zakaz_n5.wav",
]:
    datas.append((str(ROOT / name), "."))
if (ROOT / "vidaa").is_dir():
    datas.append((str(ROOT / "vidaa"), "vidaa"))
if (ROOT / "assets").is_dir():
    datas.append((str(ROOT / "assets"), "assets"))

existing = sorted(glob.glob(str(ROOT / "dist" / "ControlPS_v*.exe")))
ver = int(os.environ.get("CONTROLPS_VERSION", "203"))
if existing:
    last = Path(existing[-1]).stem
    try:
        ver = max(ver, int(last.split("_v")[-1]) + 1)
    except ValueError:
        pass
name = f"ControlPS_v{ver}"

hidden = [
    "database",
    "app",
    "app.db.database",
    "app.main",
    "app.main_legacy",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtMultimedia",
    "cryptography",
    "samsungtvws",
    "wakeonlan",
    "yaml",
    "qrcode",
    "PIL",
    "paho.mqtt.client",
    "vidaa",
    "vidaa.config",
    "vidaa.config.storage",
    "vidaa.topics",
    "vidaa.client",
    "vidaa.credentials",
    "websocket",
    "requests",
    "adb_shell",
    "certifi",
]

qt_bin = Path(sys.executable).resolve().parent / "Lib" / "site-packages" / "PyQt6" / "Qt6" / "bin"
if qt_bin.is_dir():
    os.environ["PATH"] = str(qt_bin) + os.pathsep + os.environ.get("PATH", "")

cmd = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name",
    name,
    "--distpath",
    str(ROOT / "dist"),
    "--workpath",
    str(ROOT / "build"),
    "--collect-submodules",
    "app",
    "--collect-all",
    "vidaa",
]
for hi in hidden:
    cmd.extend(["--hidden-import", hi])
for src, dest in datas:
    if Path(src).exists():
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dest}"])
cmd.append("main.py")

print(" ".join(cmd))
raise SystemExit(subprocess.call(cmd))
