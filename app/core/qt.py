from __future__ import annotations
import logging
import sys
from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
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