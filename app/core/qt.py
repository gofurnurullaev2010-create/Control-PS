from __future__ import annotations
import logging
import os
import sys
from PyQt6.QtCore import Qt, QCoreApplication, QtMsgType, qInstallMessageHandler
def configure_qt_app() -> None:
    """QApplication dan OLDIN: Win10 da UI qotishini kamaytirish."""
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')
    os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')
    try:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_CompressHighFrequencyEvents, True)
    except Exception:
        pass
    try:
        from PyQt6.QtGui import QGuiApplication, QHighDpiScaleFactorRoundingPolicy
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(QHighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
def install_exception_hook() -> None:
    """Log unexpected Python exceptions before delegating to Python\'s hook."""
    def _hook(exc_type, exc_value, exc_tb):
        logging.getLogger('control_ps').critical('Kutilmagan xatolik', exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _hook
def install_qt_message_handler() -> None:
    """Route Qt native warnings/errors into the app log."""
    def _handler(mode, _context, message: str) -> None:
        log = logging.getLogger('qt')
        text = message or ''
        if mode == QtMsgType.QtFatalMsg:
            log.critical('Qt FATAL: %s', text)
        else:
            if mode == QtMsgType.QtCriticalMsg:
                log.error('Qt: %s', text)
            else:
                if mode == QtMsgType.QtWarningMsg:
                    log.warning('Qt: %s', text)
                else:
                    log.info('Qt: %s', text)
    qInstallMessageHandler(_handler)