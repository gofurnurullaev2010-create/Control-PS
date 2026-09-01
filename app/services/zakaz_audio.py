"""QR ЗАКАЗ ovozini ijro etish — har raqam uchun alohida."""
from __future__ import annotations
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional
from app.core.paths import application_dir, resource_path
logger = logging.getLogger(__name__)
_player = None
_audio = None
def _bases() -> list[Path]:
    bases = [application_dir() / 'assets' / 'sounds', application_dir() / 'sounds', application_dir(), Path(__file__).resolve().parents[2] / 'assets' / 'sounds']
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        bases.extend([Path(meipass) / 'assets' / 'sounds', Path(meipass)])
    return bases
def zakaz_sound_path(n: int=1, prefer_wav: bool=True) -> Optional[Path]:
    """Raqamga mos ovoz: zakaz_n{N}.wav/mp3, yo\'q bo\'lsa eski zakaz_call."""
    n = max(1, min(5, int(n or 1)))
    ordered = []
    if prefer_wav:
        ordered += [f'zakaz_n{n}.wav', f'zakaz_n{n}.mp3']
    else:
        ordered += [f'zakaz_n{n}.mp3', f'zakaz_n{n}.wav']
    ordered += ['zakaz_call.wav', 'zakaz_call.mp3']
    for base in _bases():
        for name in ordered:
            p = base / name
            if p.is_file():
                return p
    for name in ordered:
        p = resource_path(name)
        if p and p.is_file():
            return p
def _play_winsound(path: Path) -> bool:
    if path.suffix.lower() != '.wav' or sys.platform != 'win32':
        return False
    else:
        try:
            import winsound
            winsound.PlaySound(str(path.resolve()), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            logger.warning('winsound: %s', e)
            return False
        else:
            return True
def _play_powershell(path: Path) -> bool:
    if sys.platform != 'win32':
        return False
    else:
        try:
            uri = path.resolve().as_uri()
            ps = f'Add-Type -AssemblyName presentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open([Uri]\'{uri}\'); Start-Sleep -Milliseconds 350; $p.Volume = 1; $p.Play(); Start-Sleep -Seconds 4; $p.Close()'
            def _run() -> None:
                subprocess.run(['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-Command', ps], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            threading.Thread(target=_run, daemon=True, name='zakaz-audio-ps').start()
        except Exception as e:
            logger.warning('PowerShell audio: %s', e)
            return False
        else:
            return True
def _play_qt(path: Path) -> bool:
    global _player
    global _audio
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        if _player is None:
            _player = QMediaPlayer()
            _audio = QAudioOutput()
            _audio.setVolume(1.0)
            _player.setAudioOutput(_audio)
        _player.stop()
        _player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        _player.play()
    except Exception as e:
        logger.warning('Qt audio: %s', e)
        return False
    else:
        return True
def play_zakaz_sound(n: int=1) -> bool:
    """«Заказ для номера N» — 1 marta."""
    path = zakaz_sound_path(n=n, prefer_wav=True)
    if path is None:
        logger.warning('zakaz audio topilmadi (n=%s)', n)
        return False
    else:
        logger.info('Zakaz audio: %s', path.name)
        if _play_winsound(path):
            return True
        else:
            if _play_powershell(path):
                return True
            else:
                return _play_qt(path)