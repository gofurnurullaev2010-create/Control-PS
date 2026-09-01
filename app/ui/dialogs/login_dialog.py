"""\nControl PS - Login oynasi\n"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
from app.auth import app_password
from app.core.paths import resource_path
class LoginDialog(QDialog):
    """Login oynasi"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Control PS - Kirish')
        self.setFixedSize(400, 250)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        logo_path = resource_path('ps_logo.png')
        if logo_path and logo_path.exists():
                self.setWindowIcon(QIcon(str(logo_path)))
        self.setStyleSheet('\n            QDialog {\n                background-color: #FFFFFF;\n                color: #1A1A1A;\n            }\n            QLineEdit {\n                background-color: #F5F5F5;\n                border: 2px solid #00D2FF;\n                border-radius: 8px;\n                padding: 10px;\n                font-size: 14px;\n                color: #1A1A1A;\n            }\n            QLineEdit:focus {\n                border-color: #3A7BD5;\n                background-color: #FFFFFF;\n            }\n            QPushButton {\n                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                color: #1A1A1A;\n                font-weight: bold;\n                border: none;\n                border-radius: 8px;\n                padding: 10px 20px;\n                font-size: 14px;\n            }\n            QPushButton:hover {\n                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3A7BD5, stop:1 #84FFFF);\n            }\n            QPushButton:pressed {\n                background-color: #00D2FF;\n            }\n            QLabel {\n                color: #1A1A1A;\n                font-size: 16px;\n            }\n        ')
        layout = QVBoxLayout()
        layout.setSpacing(20)
        title = QLabel('🎮 Control PS')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        subtitle = QLabel('Iltimos, parolni kiriting:')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText('Parol...')
        self.password_input.setMinimumHeight(40)
        layout.addWidget(self.password_input)
        button_layout = QHBoxLayout()
        login_btn = QPushButton('Kirish')
        login_btn.clicked.connect(self.login)
        login_btn.setMinimumHeight(45)
        cancel_btn = QPushButton('Chiqish')
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(45)
        button_layout.addWidget(login_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.error_label = QLabel('')
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet('color: #FF1744; font-weight: bold;')
        layout.addWidget(self.error_label)
        self.setLayout(layout)
        self.password_input.returnPressed.connect(self.login)
        self.password_input.setFocus()
    def login(self):
        """Login qilish"""
        password = self.password_input.text().strip()
        if not password:
            self.error_label.setText('Parol bo\'sh bo\'lmasligi kerak!')
            return
        else:
            if app_password.verify_password(password):
                self.accept()
                return
            else:
                self.error_label.setText('❌ Parol noto\'g\'ri!')
                self.password_input.clear()
                self.password_input.setFocus()
                QTimer.singleShot(3000, lambda: self.error_label.setText(''))