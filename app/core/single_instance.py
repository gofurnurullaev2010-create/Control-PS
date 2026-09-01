"""Bitta nusxa: ikkinchi ishga tushirish mavjud oynani oldinga chiqaradi."""
from __future__ import annotations
import logging
import sys
from typing import Callable, Optional
from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QWidget
logger = logging.getLogger(__name__)
SERVER_NAME = 'EaglePlaystation_ControlPS_SingleInstance'
def _raise_widget(w: QWidget) -> None:
    w.setWindowState(w.windowState() & ~Qt.WindowState.WindowMinimized)
    w.show()
    w.raise_()
    w.activateWindow()
    if sys.platform == 'win32':
        try:
            import ctypes
            hwnd = int(w.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            logger.warning('Oynani oldinga chiqarish: %s', e)
def activate_main_window(window: Optional[QWidget]=None) -> None:
    """Mavjud asosiy oynani (yoki birinchi ko\'rinadigan oynani) oldinga oladi."""
    app = QApplication.instance()
    if app is None:
        return
    else:
        target = window
        if target is None:
            for w in app.topLevelWidgets():
                if not isinstance(w, QWidget):
                    continue
                else:
                    if w.isWindow() and w.isVisible() and (not w.isHidden()):
                                if target is None or w.width() * w.height() > target.width() * target.height():
                                    target = w
        if target is not None:
            _raise_widget(target)
class SingleInstanceGuard(QObject):
    """QLocalServer orqali bitta instance; yangi ulanish → activate."""
    def __init__(self, app: QApplication, *, on_activate: Optional[Callable[[], None]]=None, parent: Optional[QObject]=None) -> None:
        super().__init__(parent or app)
        self._app = app
        self._on_activate = on_activate
        self._main_window = None
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
    def set_main_window(self, window: QWidget) -> None:
        self._main_window = window
    def try_become_primary(self) -> bool:
        """True = bu jarayon asosiy; False = boshqa nusxa allaqachon ochiq."""
        probe = QLocalSocket(self)
        probe.connectToServer(SERVER_NAME)
        if probe.waitForConnected(400):
            try:
                probe.write(b'ACTIVATE\n')
                probe.flush()
                probe.waitForBytesWritten(400)
            except Exception:
                pass
            try:
                probe.disconnectFromServer()
            except Exception:
                pass
            return False
        else:
            QLocalServer.removeServer(SERVER_NAME)
            if not self._server.listen(SERVER_NAME):
                QLocalServer.removeServer(SERVER_NAME)
                if not self._server.listen(SERVER_NAME):
                    logger.warning('Single-instance server listen failed: %s', self._server.errorString())
                    return True
            return True
    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            while True:
                sock = self._server.nextPendingConnection()
                if sock is None:
                    continue
                else:
                    sock.readyRead.connect(lambda s=sock: self._handle_socket(s))
                    QTimer.singleShot(50, lambda s=sock: self._handle_socket(s))
    def _handle_socket(self, sock: QLocalSocket) -> None:
        try:
            _ = bytes(sock.readAll())
        except Exception:
            pass
        try:
            sock.disconnectFromServer()
        except Exception:
            pass
        if self._on_activate:
            try:
                self._on_activate()
            except Exception as e:
                logger.warning('on_activate: %s', e)
            else:
                return
        activate_main_window(self._main_window)
def enforce_single_instance(app: QApplication) -> Optional[SingleInstanceGuard]:
    """Ikkinchi nusxa bo\'lsa False o\'rniga None qaytaradi va jarayonni yakunlash kerak.\n\n    Qaytadi: guard (asosiy) yoki None (chiqish).\n    """
    guard = SingleInstanceGuard(app)
    def _activate() -> None:
        activate_main_window(guard._main_window)
    guard._on_activate = _activate
    if not guard.try_become_primary():
        return
    else:
        app.setProperty('_controlps_single_instance', guard)
        return guard