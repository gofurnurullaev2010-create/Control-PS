"""\nAdmin Panel - Parol bilan himoyalangan admin bo\'limi\n"""
import sys
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox, QGroupBox, QFormLayout, QTabWidget, QWidget, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor
import database as db
from app.auth import app_password
class AdminLoginDialog(QDialog):
    """Admin paneli uchun login oynasi"""
    class DialogCode:
        """Dialog natijalari"""
        Accepted = 1
        Rejected = 0
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Admin Panel - Kirish')
        self.setFixedSize(350, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet('\n            QDialog {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a2e, stop:1 #16213e);\n                color: #FFFFFF;\n                border-radius: 15px;\n            }\n            QLineEdit {\n                background-color: rgba(255, 255, 255, 0.1);\n                border: 2px solid #00D2FF;\n                border-radius: 10px;\n                padding: 12px;\n                font-size: 16px;\n                color: #FFFFFF;\n                font-weight: 500;\n            }\n            QLineEdit:focus {\n                border-color: #3A7BD5;\n                background-color: rgba(255, 255, 255, 0.15);\n                box-shadow: 0 0 15px rgba(0, 210, 255, 0.3);\n            }\n            QPushButton {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                color: #000000;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 15px 30px;\n                font-size: 16px;\n                font-weight: 600;\n            }\n            QPushButton:hover {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3A7BD5, stop:1 #84FFFF);\n                transform: translateY(-2px);\n                box-shadow: 0 5px 15px rgba(0, 210, 255, 0.4);\n            }\n            QPushButton:pressed {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                transform: translateY(0px);\n            }\n            QLabel {\n                color: #FFFFFF;\n                font-size: 18px;\n                font-weight: 600;\n                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);\n            }\n        ')
        layout = QVBoxLayout()
        layout.setSpacing(20)
        title = QLabel('🔐 Admin Panel')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        password_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText('Admin parolini kiriting')
        self.password_input.setMinimumHeight(40)
        password_layout.addWidget(self.password_input)
        self.toggle_btn = QPushButton('👁')
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.clicked.connect(self.toggle_password)
        self.toggle_btn.setStyleSheet('\n            QPushButton {\n                background-color: #1A1A24;\n                border: 1px solid #444;\n                border-radius: 6px;\n                color: #888;\n                font-size: 16px;\n            }\n            QPushButton:hover {\n                background-color: #2A2A34;\n                color: #00D2FF;\n            }\n        ')
        password_layout.addWidget(self.toggle_btn)
        layout.addLayout(password_layout)
        button_layout = QHBoxLayout()
        login_btn = QPushButton('Kirish')
        login_btn.clicked.connect(self.login)
        login_btn.setMinimumHeight(40)
        cancel_btn = QPushButton('Chiqish')
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(40)
        button_layout.addWidget(login_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.error_label = QLabel('')
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet('color: #FF6B6B; font-weight: bold;')
        layout.addWidget(self.error_label)
        self.setLayout(layout)
        self.password_input.returnPressed.connect(self.login)
        self.password_input.setFocus()
    def login(self):
        """Login qilish"""
        try:
            password = self.password_input.text().strip()
            if not password:
                self.error_label.setText('Parol bo\'sh bo\'lmasligi kerak!')
                return
            else:
                if app_password.verify_admin_password(password):
                    print('Login muvaffaqiyatli!')
                    self.accept()
                else:
                    print('Login xato!')
                    self.error_label.setText('Parol noto\'g\'ri!')
                    self.password_input.clear()
                    self.password_input.setFocus()
                    QTimer.singleShot(3000, self.clear_error)
        except Exception as e:
            print(f'Login da xatolik: {e}')
            self.error_label.setText(f'Xatolik: {str(e)}')
            self.password_input.clear()
            self.password_input.setFocus()
    def clear_error(self):
        """Xabarni tozalash"""
        self.error_label.setText('')
    def toggle_password(self):
        """Parolni ko\'rsatish/yashirish"""
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText('👁‍🗨')
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText('👁')
class AdminPanelDialog(QDialog):
    """Admin paneli oynasi"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Admin Panel')
        self.setFixedSize(900, 700)
        self.setWindowFlags(Qt.WindowType.Dialog)
        self.setStyleSheet('\n            QDialog {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a2e, stop:1 #16213e);\n                color: #FFFFFF;\n                border-radius: 15px;\n            }\n            QTabWidget::pane {\n                border: 2px solid #00D2FF;\n                background: rgba(26, 26, 46, 0.8);\n                border-radius: 12px;\n                padding: 10px;\n            }\n            QTabWidget::tab-bar {\n                alignment: center;\n            }\n            QTabBar::tab {\n                background: rgba(255, 255, 255, 0.1);\n                border: 1px solid #00D2FF;\n                border-radius: 8px;\n                padding: 12px 24px;\n                margin-right: 5px;\n                font-weight: 600;\n                font-size: 14px;\n                color: #FFFFFF;\n            }\n            QTabBar::tab:selected {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                color: #000000;\n            }\n            QTabBar::tab:hover {\n                background: rgba(0, 210, 255, 0.2);\n                transform: translateY(-1px);\n            }\n            QGroupBox {\n                background: rgba(255, 255, 255, 0.05);\n                border: 2px solid #00D2FF;\n                border-radius: 10px;\n                font-size: 16px;\n                font-weight: 600;\n                padding-top: 20px;\n                color: #FFFFFF;\n                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 20px;\n                padding: 0 10px;\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                border-radius: 5px;\n                color: #000000;\n            }\n            QPushButton {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                color: #000000;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 12px 24px;\n                font-size: 16px;\n                font-weight: 600;\n            }\n            QPushButton:hover {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3A7BD5, stop:1 #84FFFF);\n                transform: translateY(-2px);\n                box-shadow: 0 5px 15px rgba(0, 210, 255, 0.4);\n            }\n            QPushButton:pressed {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A7BD5);\n                transform: translateY(0px);\n            }\n            QSpinBox, QDoubleSpinBox {\n                background: rgba(255, 255, 255, 0.1);\n                border: 2px solid #00D2FF;\n                border-radius: 8px;\n                padding: 8px;\n                font-size: 14px;\n                color: #FFFFFF;\n                font-weight: 500;\n            }\n            QSpinBox:focus, QDoubleSpinBox:focus {\n                border-color: #3A7BD5;\n                background: rgba(255, 255, 255, 0.15);\n                box-shadow: 0 0 10px rgba(0, 210, 255, 0.3);\n            }\n            QScrollArea {\n                background: transparent;\n                border: none;\n            }\n            QScrollBar:vertical {\n                background: rgba(255, 255, 255, 0.1);\n                width: 12px;\n                border-radius: 6px;\n            }\n            QScrollBar::handle:vertical {\n                background: #00D2FF;\n                border-radius: 6px;\n                min-height: 20px;\n            }\n            QScrollBar::handle:vertical:hover {\n                background: #3A7BD5;\n            }\n        ')
        self.tabs = QTabWidget()
        self.create_prices_tab()
        self.create_stations_count_tab()
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    def create_prices_tab(self):
        """Stollar narxlari tabini yaratish"""
        prices_widget = QWidget()
        layout = QVBoxLayout()
        prices_group = QGroupBox('Har bir stol narxi')
        prices_layout = QVBoxLayout()
        title_label = QLabel('Har bir stol uchun alohida narx belgilang:')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #00D2FF; margin-bottom: 10px;')
        prices_layout.addWidget(title_label)
        self.price_inputs = {}
        station_prices = db.get_all_station_prices()
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        for i, station_id in enumerate(sorted(station_prices.keys())):
            station_layout = QHBoxLayout()
            station_label = QLabel(station_id)
            station_label.setStyleSheet('\n                QLabel {\n                    background-color: #2D334A;\n                    color: #FFFFFF;\n                    padding: 8px 12px;\n                    border-radius: 6px;\n                    font-weight: bold;\n                    min-width: 80px;\n                    text-align: center;\n                }\n            ')
            station_layout.addWidget(station_label)
            price_input = QDoubleSpinBox()
            price_input.setRange(1000, 100000)
            price_input.setValue(station_prices[station_id])
            price_input.setSuffix(' so\'m/soat')
            price_input.setMinimumWidth(150)
            price_input.setStyleSheet('\n                QDoubleSpinBox {\n                    background-color: #1E2139;\n                    color: #FFFFFF;\n                    border: 2px solid #444;\n                    border-radius: 6px;\n                    padding: 8px;\n                    font-size: 14px;\n                }\n                QDoubleSpinBox:focus {\n                    border-color: #00D2FF;\n                }\n            ')
            self.price_inputs[station_id] = price_input
            station_layout.addWidget(price_input)
            station_layout.addStretch()
            scroll_layout.addLayout(station_layout)
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        prices_layout.addWidget(scroll)
        prices_group.setLayout(prices_layout)
        layout.addWidget(prices_group)
        save_btn = QPushButton('Narxlarni saqlash')
        save_btn.setStyleSheet('\n            QPushButton {\n                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #00A8FF);\n                color: #FFFFFF;\n                font-weight: bold;\n                font-size: 16px;\n                border: none;\n                border-radius: 8px;\n                padding: 12px 24px;\n            }\n            QPushButton:hover {\n                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00A8FF, stop:1 #0088FF);\n            }\n        ')
        save_btn.clicked.connect(self.save_prices)
        save_btn.setMinimumHeight(50)
        layout.addWidget(save_btn)
        layout.addStretch()
        prices_widget.setLayout(layout)
        self.tabs.addTab(prices_widget, 'Narxlar')
    def create_stations_count_tab(self):
        """Stollar sonini boshqarish tabini yaratish"""
        stations_count_widget = QWidget()
        layout = QVBoxLayout()
        count_group = QGroupBox('Stollar sonini boshqarish')
        count_layout = QVBoxLayout()
        current_count = db.get_station_count()
        count_label = QLabel(f'Hozirgi stollar soni: {current_count} ta')
        count_label.setStyleSheet('font-size: 18px; font-weight: bold; color: #00D2FF; margin: 10px;')
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.addWidget(count_label)
        count_input_layout = QHBoxLayout()
        count_input_layout.addWidget(QLabel('Yangi stollar soni:'))
        self.station_count_input = QSpinBox()
        self.station_count_input.setRange(1, 20)
        self.station_count_input.setValue(current_count)
        self.station_count_input.setSuffix(' ta')
        self.station_count_input.setMinimumWidth(150)
        count_input_layout.addWidget(self.station_count_input)
        count_input_layout.addStretch()
        count_layout.addLayout(count_input_layout)
        buttons_layout = QHBoxLayout()
        increase_btn = QPushButton('1 ta Qo\'shish')
        increase_btn.clicked.connect(self.increase_station_count)
        increase_btn.setMinimumHeight(40)
        decrease_btn = QPushButton('1 ta Kamaytirish')
        decrease_btn.clicked.connect(self.decrease_station_count)
        decrease_btn.setMinimumHeight(40)
        apply_btn = QPushButton('Saqlash')
        apply_btn.clicked.connect(self.apply_station_count)
        apply_btn.setStyleSheet('\n            QPushButton {\n                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2ED1FF, stop:1 #00D2FF);\n                color: #000000;\n                font-weight: bold;\n                font-size: 16px;\n            }\n        ')
        apply_btn.setMinimumHeight(50)
        buttons_layout.addWidget(increase_btn)
        buttons_layout.addWidget(decrease_btn)
        buttons_layout.addWidget(apply_btn)
        count_layout.addLayout(buttons_layout)
        info_label = QLabel('Stollar sonini o\'zgartirganda barcha ma\'lumotlar saqlanadi!\nMaksimal 20 ta stol qo\'shishingiz mumkin.')
        info_label.setStyleSheet('color: #8A8D93; font-size: 12px; margin-top: 20px;')
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.addWidget(info_label)
        count_group.setLayout(count_layout)
        layout.addWidget(count_group)
        layout.addStretch()
        stations_count_widget.setLayout(layout)
        self.tabs.addTab(stations_count_widget, 'Stollar soni')
    def increase_station_count(self):
        """Stollar sonini 1 taga ko\'paytirish"""
        current = self.station_count_input.value()
        if current < 20:
            self.station_count_input.setValue(current + 1)
    def decrease_station_count(self):
        """Stollar sonini 1 taga kamaytirish"""
        current = self.station_count_input.value()
        if current > 1:
            self.station_count_input.setValue(current - 1)
    def apply_station_count(self):
        """Stollar sonini saqlash"""
        new_count = self.station_count_input.value()
        current_count = db.get_station_count()
        if new_count == current_count:
            QMessageBox.information(self, 'Ma\'lumot', f'Stollar soni o\'zgartirilmadi: {new_count} ta')
            return
        else:
            reply = QMessageBox.question(self, 'Stollar sonini o\'zgartirish', f'Stollar sonini {current_count} dan {new_count} ga o\'zgartirmoqchimisiz?\n\nBarcha ma\'lumotlar saqlanadi!', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                pass
        db.update_station_count(new_count)
        QMessageBox.information(self, 'Muvaffaqiyatli', f'Stollar soni {new_count} taga o\'zgartirildi!\n\nEkran avtomatik yangilanadi!')
        count_label = self.tabs.findChildren(QLabel)[0]
        count_label.setText(f'Hozirgi stollar soni: {new_count} ta')
        main_window = self.parent()
        try:
            if main_window and hasattr(main_window, 'refresh_all_cards'):
                main_window.refresh_all_cards()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Stollar sonini o\'zgartirishda xatolik: {str(e)}')
    def save_prices(self):
        """Narxlarni saqlash"""
        try:
            saved_prices = []
            for station_id, price_input in self.price_inputs.items():
                old_price = db.get_station_price(station_id)
                new_price = price_input.value()
                db.set_station_price(station_id, new_price)
                saved_prices.append(f'{station_id}: {old_price:,.0f} -> {new_price:,.0f}')
            details = '\n'.join(saved_prices[:5])
            if len(saved_prices) > 5:
                details += f'\n... va {len(saved_prices) - 5} ta stol narxi'
            QMessageBox.information(self, 'Narxlar saqlandi!', f'Har bir stol narxi muvaffaqiyatli saqlandi!\n\n{details}')
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Narxlarni saqlashda xatolik: {str(e)}')