# -*- coding: utf-8 -*-
"""ControlPS_v*.exe yig'ish (PyInstaller).

Standart: onedir (papka) — Windows Defender onefile ni tez-tez virus deb belgilaydi.
Eski usul: set CONTROLPS_ONEFILE=1
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

ONEFILE = os.environ.get("CONTROLPS_ONEFILE", "").strip().lower() in ("1", "true", "yes", "on")

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
if (ROOT / "platform-tools" / "adb.exe").is_file():
    datas.append((str(ROOT / "platform-tools"), "platform-tools"))

existing = sorted(
    glob.glob(str(ROOT / "dist" / "ControlPS_v*.exe"))
    + glob.glob(str(ROOT / "dist" / "ControlPS_v*" / "ControlPS_v*.exe"))
)
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

(ROOT / "build").mkdir(parents=True, exist_ok=True)
ver_file = ROOT / "build" / "file_version_info.txt"
ver_file.write_text(
    f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({ver}, 0, 0, 0),
    prodvers=({ver}, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Eagle Playstation'),
          StringStruct('FileDescription', 'Control PS — klub kassa va TV boshqaruvi'),
          StringStruct('FileVersion', '{ver}.0.0.0'),
          StringStruct('InternalName', 'ControlPS'),
          StringStruct('LegalCopyright', 'Eagle Playstation'),
          StringStruct('OriginalFilename', '{name}.exe'),
          StringStruct('ProductName', 'Control PS'),
          StringStruct('ProductVersion', '{ver}.0.0.0'),
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
    encoding="utf-8",
)

cmd = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--noupx",
    "--name",
    name,
    "--distpath",
    str(ROOT / "dist"),
    "--workpath",
    str(ROOT / "build"),
    "--version-file",
    str(ver_file),
    "--collect-submodules",
    "app",
    "--collect-all",
    "vidaa",
]
if ONEFILE:
    cmd.append("--onefile")
else:
    cmd.append("--onedir")
for hi in hidden:
    cmd.extend(["--hidden-import", hi])
for src, dest in datas:
    if Path(src).exists():
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dest}"])
cmd.append("main.py")

print(" ".join(cmd))
code = subprocess.call(cmd)
dist_dir = ROOT / "dist"
app_dir = dist_dir / name if not ONEFILE else dist_dir
if code == 0:
    apk = ROOT / "controlps-lock.apk"
    if apk.is_file():
        shutil.copy2(apk, app_dir / "controlps-lock.apk")
    src_pt = ROOT / "platform-tools"
    dst_pt = app_dir / "platform-tools"
    if (src_pt / "adb.exe").is_file():
        dst_pt.mkdir(parents=True, exist_ok=True)
        for item in src_pt.iterdir():
            if item.is_file():
                shutil.copy2(item, dst_pt / item.name)
    print(f"Ishga tushirish: {app_dir / (name + '.exe')}")
raise SystemExit(code)
