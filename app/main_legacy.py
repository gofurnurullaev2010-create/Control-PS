"""\nLegacy entrypoint (CONTROL_PS_LEGACY=1).\n\nEski ui_manager / legacy_main_window shell.\n"""
from __future__ import annotations
import logging
import sys
from PyQt6.QtCore import Qt, QTimer, qInstallMessageHandler, QtMsgType
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QSplashScreen
from app.auth import license_manager
from app.core.paths import resource_path
from app.core.qt import configure_qt_app, install_exception_hook
from app.core.runtime import ensure_tv_tools_path, setup_logging
from app.core.single_instance import enforce_single_instance
from app.db.legacy import init as init_database
from app.tv import tv_handler, tv_platforms
from app.ui.dialogs.login_dialog import LoginDialog
from app.ui.legacy_main_window import MainWindow
def _qt_message_handler(mode, context, message: str) -> None:
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
def main() -> None:
    setup_logging()
    ensure_tv_tools_path()
    configure_qt_app()
    install_exception_hook()
    qInstallMessageHandler(_qt_message_handler)
    init_database()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    guard = enforce_single_instance(app)
    if guard is None:
        sys.exit(0)
    splash = None
    logo_path = resource_path('ps_logo.png')
    if logo_path and logo_path.exists():
            app.setWindowIcon(QIcon(str(logo_path)))
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(600, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                splash = QSplashScreen(scaled, Qt.WindowType.WindowStaysOnTopHint)
                splash.show()
                splash.showMessage('Control PS - Tekshirilmoqda...', Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
                app.processEvents()
    try:
        lic = license_manager.verify_license_full()
        if not lic.valid:
            if splash:
                splash.close()
            app.clipboard().setText(lic.hwid)
            detail = lic.message or 'Litsenziya fayli topilmadi yoki noto\'g\'ri.'
            logging.getLogger('control_ps').error('Litsenziya rad etildi: %s', detail)
            QMessageBox.critical(None, 'Litsenziya xatosi', f'{detail}\n\nKompyuter kodi (HWID): {lic.hwid}\n\n(HWID nusxalandi. Dasturchiga yuborib license.key oling.)')
            sys.exit(1)
    except Exception as e:
        if splash:
            splash.close()
        logging.getLogger('control_ps').critical('Litsenziya tizimi xatosi', exc_info=True)
        QMessageBox.critical(None, 'Litsenziya tizimi xatosi', f'Xatolik: {e}')
        sys.exit(1)
    if splash:
        splash.showMessage('Control PS - Yuklanmoqda...', Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
        app.processEvents()
    login = LoginDialog()
    if splash:
        QTimer.singleShot(1500, splash.close)
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    try:
        win = MainWindow()
        guard.set_main_window(win)
        win.show()
        ensure_tv_tools_path()
        tv_platforms.prepare_webos_cli()
        tv_platforms.sync_webos_device_mappings_from_ares()
        tv_platforms.warmup_webos_devices()
        tv_handler.start_lock_gate_http_server()
        tv_handler.sync_active_tv_sessions_from_db()
        tv_handler.set_main_app_lock_gate(True)
        tv_handler.sync_webos_initial_lock_from_db()
        tv_handler.start_webos_connectivity_monitor()
        tv_handler.broadcast_lock_gate_url_to_all_android_tvs_background()
        app.aboutToQuit.connect(lambda: tv_handler.set_main_app_lock_gate(False))
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, 'Xatolik', f'Dasturni ishga tushirishda xatolik yuz berdi:\n\n{e}')
        sys.exit(1)
if __name__ == '__main__':
    main()