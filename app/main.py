"""\nModular Control PS entrypoint (standart).\n\nIshga tushirish:\n  python main.py\n  python -m app.main\n\nLegacy shell:\n  set CONTROL_PS_LEGACY=1 && python main.py\n"""
from __future__ import annotations
import sys
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QSplashScreen
from app.ui.dialogs.login_dialog import LoginDialog
from app.core.bootstrap import prepare_runtime
from app.core.container import build_container
from app.core.paths import resource_path
from app.core.qt import install_exception_hook, install_qt_message_handler
from app.core.single_instance import enforce_single_instance
from app.db.legacy import init as init_database
from app.ui.main_window import MainWindow
def _show_splash(app: QApplication) -> QSplashScreen | None:
    logo_path = resource_path('ps_logo.png')
    if not logo_path or not logo_path.exists():
        return None
    else:
        app.setWindowIcon(QIcon(str(logo_path)))
        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            return
        else:
            scaled = pixmap.scaled(600, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            splash = QSplashScreen(scaled, Qt.WindowType.WindowStaysOnTopHint)
            splash.show()
            splash.showMessage('Eagle Playstation - Tekshirilmoqda...', Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
            app.processEvents()
            return splash
def main() -> None:
    prepare_runtime()
    install_exception_hook()
    install_qt_message_handler()
    init_database()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    guard = enforce_single_instance(app)
    if guard is None:
        sys.exit(0)
    splash = _show_splash(app)
    container = build_container()
    lic = container.license.verify()
    if not lic.valid:
        if splash:
            splash.close()
        app.clipboard().setText(lic.hwid)
        QMessageBox.critical(None, 'Litsenziya xatosi', f"{lic.message or 'Litsenziya fayli topilmadi.'}\n\nHWID: {lic.hwid}")
        sys.exit(1)
    if splash:
        splash.showMessage('Eagle Playstation - Yuklanmoqda...', Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
        app.processEvents()
    login = LoginDialog()
    if splash:
        QTimer.singleShot(1500, splash.close)
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    try:
        win = MainWindow(container)
        guard.set_main_window(win)
        win.show()
        container.tv.bootstrap_after_login()
        app.aboutToQuit.connect(container.tv.shutdown)
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, 'Xatolik', f'Dasturni ishga tushirishda xatolik:\n\n{e}')
        sys.exit(1)
if __name__ == '__main__':
    main()