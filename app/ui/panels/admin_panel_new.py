"""\nAdmin Panel - Parol o\'zgartirish bilan\n"""
import sys
import hashlib
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QGroupBox, QFormLayout, QTabWidget, QWidget, QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit, QScrollArea, QDateEdit, QTimeEdit, QInputDialog, QCheckBox, QFileDialog, QGridLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QTime
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon, QGuiApplication, QPixmap
import database as db
from app.auth import app_password
from app.core.paths import resource_path
BG_MAIN = '#FFFFFF'
BG_HEADER = '#F5F6F8'
BG_CARD = '#FFFFFF'
TEXT_PRIMARY = '#202124'
TEXT_SECONDARY = '#5F6368'
ACCENT = '#6B7C3B'
COL_GREEN = '#16A34A'
COL_RED = '#DC2626'
BORDER = '#E5E7EB'
def _resource_path(filename: str) -> Path:
    """PyInstaller bilan ishlaydigan resurs yo\'li olish."""
    p = resource_path(filename)
    if p is not None:
        return p
    else:
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / filename
        else:
            return Path(__file__).resolve().parents[3] / filename
class AdminLoginDialog(QDialog):
    """Admin paneli uchun login oynasi"""
    class DialogCode:
        """Dialog natijalari"""
        Accepted = 1
        Rejected = 0
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Admin Panel - Kirish')
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        logo_path = _resource_path('ps_logo.png')
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setStyleSheet(f'\n            QDialog {{\n                background: {BG_MAIN};\n                color: {TEXT_PRIMARY};\n                border-radius: 15px;\n            }}\n            QLineEdit {{\n                background-color: {BG_CARD};\n                border: 2px solid {ACCENT};\n                border-radius: 10px;\n                padding: 12px;\n                font-size: 16px;\n                color: {TEXT_PRIMARY};\n                font-weight: 500;\n            }}\n            QLineEdit:focus {{\n                border-color: #67E8F9;\n                background-color: {BG_HEADER};\n            }}\n            QPushButton {{\n                background: {ACCENT};\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 15px 30px;\n                font-size: 16px;\n                font-weight: 600;\n            }}\n            QPushButton:hover {{\n                background: #67E8F9;\n            }}\n            QPushButton:pressed {{\n                background: {ACCENT};\n            }}\n            QLabel {{\n                color: {TEXT_PRIMARY};\n                font-size: 18px;\n                font-weight: 600;\n            }}\n        ')
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
        self.password_input.setPlaceholderText('Parolni kiriting...')
        self.password_input.setMinimumHeight(40)
        password_layout.addWidget(self.password_input)
        self.toggle_btn = QPushButton('👁')
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.clicked.connect(self.toggle_password)
        self.toggle_btn.setStyleSheet(f'\n            QPushButton {{\n                background-color: {BG_CARD};\n                border: 1px solid {ACCENT};\n                border-radius: 6px;\n                color: {ACCENT};\n                font-size: 16px;\n            }}\n            QPushButton:hover {{\n                background-color: {ACCENT};\n                color: #FFFFFF;\n            }}\n        ')
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
        self.error_label.setStyleSheet('color: #FF4D4D; font-weight: bold; font-size: 14px;')
        layout.addWidget(self.error_label)
        self.setLayout(layout)
        self.password_input.returnPressed.connect(self.login)
        self.password_input.setFocus()
    def toggle_password(self):
        """Parolni ko\'rsatish/yashirish"""
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText('👁‍🗨')
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText('👁')
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
                    self.error_label.setText('Noto\'g\'ri parol! Qayta urinib ko\'ring.')
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
class ChangePasswordDialog(QDialog):
    """Parol o\'zgartirish dialogi"""
    def __init__(self, current_password, parent=None):
        super().__init__(parent)
        self.current_password = current_password
        self.new_password = ''
        self.setWindowTitle('Parolni O\'zgartirish')
        self.setFixedSize(400, 350)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(f'\n            QDialog {{\n                background: {BG_MAIN};\n                color: {TEXT_PRIMARY};\n                border-radius: 15px;\n            }}\n            QLineEdit {{\n                background-color: {BG_CARD};\n                border: 2px solid {ACCENT};\n                border-radius: 10px;\n                padding: 12px;\n                font-size: 16px;\n                color: {TEXT_PRIMARY};\n                font-weight: 500;\n            }}\n            QLineEdit:focus {{\n                border-color: #67E8F9;\n                background-color: {BG_HEADER};\n            }}\n            QPushButton {{\n                background: {ACCENT};\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 15px 30px;\n                font-size: 16px;\n                font-weight: 600;\n            }}\n            QPushButton:hover {{\n                background: #67E8F9;\n            }}\n            QPushButton:pressed {{\n                background: {ACCENT};\n            }}\n            QLabel {{\n                color: {ACCENT};\n                font-size: 16px;\n                font-weight: 600;\n            }}\n        ')
        layout = QVBoxLayout()
        layout.setSpacing(20)
        title = QLabel('🔐 Parolni O\'zgartirish')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        form_layout = QFormLayout()
        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_password_input.setPlaceholderText('Eski parol...')
        form_layout.addRow('Eski parol:', self.old_password_input)
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText('Yangi parol...')
        form_layout.addRow('Yangi parol:', self.new_password_input)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setPlaceholderText('Yangi parolni tasdiqlash...')
        form_layout.addRow('Tasdiqlash:', self.confirm_password_input)
        layout.addLayout(form_layout)
        self.error_label = QLabel('')
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet('color: #FF4D4D; font-weight: bold; font-size: 14px;')
        layout.addWidget(self.error_label)
        button_layout = QHBoxLayout()
        save_btn = QPushButton('Saqlash')
        save_btn.clicked.connect(self.save_password)
        save_btn.setMinimumHeight(40)
        cancel_btn = QPushButton('Bekor qilish')
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(40)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    def save_password(self):
        """Parol saqlash"""
        try:
            old_password = self.old_password_input.text().strip()
            new_password = self.new_password_input.text().strip()
            confirm_password = self.confirm_password_input.text().strip()
            if not old_password or not new_password or (not confirm_password):
                self.error_label.setText('Barcha maydonlarni to\'ldiring!')
                return
            else:
                if not app_password.verify_admin_password(old_password):
                    self.error_label.setText('Eski parol noto\'g\'ri!')
                    return
                else:
                    if new_password != confirm_password:
                        self.error_label.setText('Yangi parollar mos kelmadi!')
                        return
                    else:
                        if len(new_password) < 4:
                            self.error_label.setText('Yangi parol kamida 4 belgidan iborat bo\'lishi kerak!')
                            return
                        else:
                            if app_password.change_admin_password(new_password):
                                self.new_password = new_password
                                self.accept()
                            else:
                                self.error_label.setText('Parol saqlashda xatolik!')
        except Exception as e:
            print(f'Parol saqlashda xatolik: {e}')
            self.error_label.setText(f'Xatolik: {str(e)}')
    def get_new_password(self):
        """Yangi parolni olish"""
        return self.new_password
class AdminPanelDialog(QDialog):
    """Admin paneli oynasi"""
    station_count_changed = pyqtSignal(int)
    station_settings_changed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Admin Panel')
        self.setFixedSize(1100, 760)
        self.setWindowFlags(Qt.WindowType.Dialog)
        logo_path = _resource_path('ps_logo.png')
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setStyleSheet(f'\n            QDialog {{\n                background: {BG_MAIN};\n                color: {TEXT_PRIMARY};\n                border-radius: 15px;\n            }}\n            QTabWidget::pane {{\n                border: 1px solid {BORDER};\n                background: {BG_HEADER};\n                border-radius: 12px;\n                padding: 10px;\n            }}\n            QTabWidget::tab-bar {{\n                alignment: center;\n            }}\n            QTabBar::tab {{\n                background: {BG_CARD};\n                border: 1px solid {BORDER};\n                border-radius: 8px;\n                padding: 12px 24px;\n                margin-right: 5px;\n                font-weight: 600;\n                font-size: 14px;\n                color: {TEXT_SECONDARY};\n            }}\n            QTabBar::tab:selected {{\n                background: {ACCENT};\n                color: #FFFFFF;\n            }}\n            QTabBar::tab:hover {{\n                background: rgba(34, 211, 238, 0.18);\n            }}\n            QGroupBox {{\n                background: rgba(255,255,255,0.02);\n                border: 1px solid {BORDER};\n                border-radius: 10px;\n                font-size: 16px;\n                font-weight: 600;\n                padding-top: 20px;\n                margin-top: 16px;\n                color: {ACCENT};\n            }}\n            QGroupBox::title {{\n                subcontrol-origin: margin;\n                left: 20px;\n                padding: 0 10px;\n                color: {ACCENT};\n            }}\n            QLabel {{\n                color: {TEXT_PRIMARY};\n            }}\n            QPushButton {{\n                background: {ACCENT};\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 12px 24px;\n                font-size: 16px;\n                font-weight: 600;\n            }}\n            QPushButton:hover {{\n                background: #67E8F9;\n            }}\n            QPushButton:pressed {{\n                background: {ACCENT};\n            }}\n            QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTimeEdit, QLineEdit {{\n                background: {BG_CARD};\n                border: 1px solid {BORDER};\n                border-radius: 8px;\n                padding: 8px;\n                font-size: 14px;\n                color: {TEXT_PRIMARY};\n                font-weight: 500;\n            }}\n            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,\n            QDateEdit:focus, QTimeEdit:focus, QLineEdit:focus {{\n                border: 1px solid {ACCENT};\n                background: {BG_HEADER};\n            }}\n            QComboBox QAbstractItemView {{\n                background-color: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                selection-background-color: {ACCENT};\n                selection-color: #FFFFFF;\n                border: 1px solid {ACCENT};\n                outline: none;\n            }}\n            QTextEdit {{\n                background: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER};\n                border-radius: 8px;\n            }}\n            QTableWidget {{\n                background: {BG_HEADER};\n                color: {TEXT_PRIMARY};\n                gridline-color: {BORDER};\n                border: none;\n            }}\n            QHeaderView::section {{\n                background: {BG_CARD};\n                color: {ACCENT};\n                padding: 8px;\n                font-weight: 800;\n                border: 1px solid {BORDER};\n            }}\n            QScrollArea {{\n                background: {BG_HEADER};\n                border: 1px solid {BORDER};\n                border-radius: 12px;\n            }}\n            QScrollArea > QWidget > QWidget {{\n                background: {BG_HEADER};\n            }}\n            QScrollBar:vertical {{\n                background: rgba(255, 255, 255, 0.04);\n                width: 12px;\n                border-radius: 6px;\n            }}\n            QScrollBar::handle:vertical {{\n                background: rgba(255,255,255,0.18);\n                border-radius: 6px;\n                min-height: 20px;\n            }}\n            QScrollBar::handle:vertical:hover {{\n                background: rgba(255,255,255,0.30);\n            }}\n        ')
        self.tabs = QTabWidget()
        self.create_combined_prices_tab()
        self.create_daily_report_tab()
        self.create_day_settings_tab()
        self.create_license_tab()
        self.create_password_tab()
        self.create_operator_reports_tab()
        self.create_telegram_tab()
        self.create_zakaz_qr_tab()
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    def create_prices_tab(self):
        """Stollar narxlari tabini yaratish"""
        prices_widget = QWidget()
        layout = QVBoxLayout()
        self.price_inputs = {}
        self.name_inputs = {}
        self.price_slot_inputs = {}
        station_ids = db.list_station_ids()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        for i, station_id in enumerate(station_ids):
            group = QGroupBox(f'{station_id}')
            group_layout = QFormLayout()
            name_input = QLineEdit()
            name_input.setPlaceholderText('Masalan: KABINA, VIP-1, ZAL-A')
            name_input.setText(db.get_station_display_name(station_id))
            name_input.setMinimumWidth(220)
            price_input = QDoubleSpinBox()
            price_input.setRange(0, 1000000)
            price_input.setSuffix(' so\'m')
            price_input.setDecimals(0)
            price_input.setValue(db.get_station_price(station_id))
            price_input.setMinimumWidth(200)
            slots = db.get_station_price_slots(station_id)
            if len(slots) < 2:
                base_price = db.get_station_price(station_id)
                slots = [{'start_minute': 540, 'end_minute': 1080, 'hourly_rate': base_price}, {'start_minute': 1080, 'end_minute': 540, 'hourly_rate': base_price}]
            slot_widgets = []
            self.price_inputs[station_id] = price_input
            self.name_inputs[station_id] = name_input
            group_layout.addRow('Ko\'rinadigan nom:', name_input)
            group_layout.addRow('Asosiy soatbay narx:', price_input)
            for slot_idx, slot in enumerate(slots[:2], start=1):
                row = QHBoxLayout()
                start_time = QTimeEdit()
                start_time.setDisplayFormat('HH:mm')
                start_minute = int(slot.get('start_minute', 0))
                start_time.setTime(QTime(start_minute // 60, start_minute % 60))
                end_time = QTimeEdit()
                end_time.setDisplayFormat('HH:mm')
                end_minute = int(slot.get('end_minute', 0))
                end_time.setTime(QTime(end_minute // 60, end_minute % 60))
                slot_price = QDoubleSpinBox()
                slot_price.setRange(0, 1000000)
                slot_price.setSuffix(' so\'m')
                slot_price.setDecimals(0)
                slot_price.setValue(float(slot.get('hourly_rate', price_input.value()) or 0))
                slot_price.setMinimumWidth(160)
                row.addWidget(QLabel('dan'))
                row.addWidget(start_time)
                row.addWidget(QLabel('gacha'))
                row.addWidget(end_time)
                row.addWidget(slot_price)
                group_layout.addRow(f'Tarif {slot_idx}:', row)
                slot_widgets.append((start_time, end_time, slot_price))
            self.price_slot_inputs[station_id] = slot_widgets
            group.setLayout(group_layout)
            scroll_layout.addWidget(group)
        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_content.setStyleSheet(f'background: {BG_HEADER};')
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        save_btn = QPushButton('💾 Nomlar va narxlarni saqlash')
        save_btn.clicked.connect(self.save_prices)
        save_btn.setMinimumHeight(50)
        layout.addWidget(save_btn)
        prices_widget.setLayout(layout)
    def create_stations_count_tab(self):
        """Stollarni boshqarish tabini yaratish"""
        count_widget = QWidget()
        layout = QVBoxLayout()
        count_group = QGroupBox('Stollar soni')
        count_layout = QHBoxLayout()
        self.station_count = QSpinBox()
        self.station_count.setRange(1, 50)
        self.station_count.setValue(len(db.list_station_ids()))
        self.station_count.setSuffix(' ta')
        self.station_count.setMinimumWidth(200)
        count_layout.addWidget(self.station_count)
        count_layout.addStretch()
        count_group.setLayout(count_layout)
        layout.addWidget(count_group)
        save_btn = QPushButton('💾 Stollar sonini saqlash')
        save_btn.clicked.connect(self.save_station_count)
        save_btn.setMinimumHeight(50)
        layout.addWidget(save_btn)
        self.change_password_btn = QPushButton('PAROLNI O\'ZGARTIRISH')
        self.change_password_btn.clicked.connect(self.change_password)
        self.change_password_btn.setMinimumHeight(40)
        layout.addWidget(self.change_password_btn)
        count_widget.setLayout(layout)
    def create_combined_prices_tab(self):
        """Narxlar tabi - stollar soni va narxlari birga"""
        combined_widget = QWidget()
        layout = QVBoxLayout()
        count_group = QGroupBox('Stollar soni')
        count_layout = QHBoxLayout()
        self.station_count = QSpinBox()
        self.station_count.setRange(1, 50)
        self.station_count.setValue(len(db.list_station_ids()))
        self.station_count.setSuffix(' ta')
        self.station_count.setMinimumWidth(200)
        count_layout.addWidget(self.station_count)
        count_layout.addStretch()
        count_group.setLayout(count_layout)
        layout.addWidget(count_group)
        save_count_btn = QPushButton('💾 Stollar sonini saqlash')
        save_count_btn.clicked.connect(self.save_station_count)
        save_count_btn.setMinimumHeight(40)
        layout.addWidget(save_count_btn)
        joy_group = QGroupBox('Jostik narxi (2 tadan ortiq — soatiga, har bir qo\'shimcha jostik)')
        joy_layout = QHBoxLayout()
        self.joystick_price = QSpinBox()
        self.joystick_price.setRange(0, 10000000)
        self.joystick_price.setSingleStep(500)
        self.joystick_price.setSuffix(' so\'m/soat')
        self.joystick_price.setMinimumWidth(200)
        try:
            self.joystick_price.setValue(int(db.get_joystick_price()))
        except Exception:
            self.joystick_price.setValue(3000)
        joy_layout.addWidget(self.joystick_price)
        joy_layout.addStretch()
        joy_group.setLayout(joy_layout)
        layout.addWidget(joy_group)
        save_joy_btn = QPushButton('💾 Jostik narxini saqlash')
        save_joy_btn.clicked.connect(self.save_joystick_price)
        save_joy_btn.setMinimumHeight(40)
        layout.addWidget(save_joy_btn)
        prices_group = QGroupBox('Stollar narxlari')
        prices_layout = QVBoxLayout()
        self.price_inputs = {}
        self.name_inputs = {}
        self.price_slot_inputs = {}
        station_ids = db.list_station_ids()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        for i, station_id in enumerate(station_ids):
            group = QGroupBox(f'{station_id}')
            group_layout = QFormLayout()
            name_input = QLineEdit()
            name_input.setPlaceholderText('Masalan: KABINA, VIP-1, ZAL-A')
            name_input.setText(db.get_station_display_name(station_id))
            name_input.setMinimumWidth(220)
            price_input = QDoubleSpinBox()
            price_input.setRange(0, 1000000)
            price_input.setSuffix(' so\'m')
            price_input.setDecimals(0)
            price_input.setValue(db.get_station_price(station_id))
            price_input.setMinimumWidth(200)
            slots = db.get_station_price_slots(station_id)
            if len(slots) < 2:
                base_price = db.get_station_price(station_id)
                slots = [{'start_minute': 540, 'end_minute': 1080, 'hourly_rate': base_price}, {'start_minute': 1080, 'end_minute': 540, 'hourly_rate': base_price}]
            slot_widgets = []
            self.price_inputs[station_id] = price_input
            self.name_inputs[station_id] = name_input
            group_layout.addRow('Ko\'rinadigan nom:', name_input)
            group_layout.addRow('Asosiy soatbay narx:', price_input)
            for slot_idx, slot in enumerate(slots[:2], start=1):
                row = QHBoxLayout()
                start_time = QTimeEdit()
                start_time.setDisplayFormat('HH:mm')
                start_minute = int(slot.get('start_minute', 0))
                start_time.setTime(QTime(start_minute // 60, start_minute % 60))
                end_time = QTimeEdit()
                end_time.setDisplayFormat('HH:mm')
                end_minute = int(slot.get('end_minute', 0))
                end_time.setTime(QTime(end_minute // 60, end_minute % 60))
                slot_price = QDoubleSpinBox()
                slot_price.setRange(0, 1000000)
                slot_price.setSuffix(' so\'m')
                slot_price.setDecimals(0)
                slot_price.setValue(float(slot.get('hourly_rate', price_input.value()) or 0))
                slot_price.setMinimumWidth(160)
                row.addWidget(QLabel('dan'))
                row.addWidget(start_time)
                row.addWidget(QLabel('gacha'))
                row.addWidget(end_time)
                row.addWidget(slot_price)
                group_layout.addRow(f'Tarif {slot_idx}:', row)
                slot_widgets.append((start_time, end_time, slot_price))
            self.price_slot_inputs[station_id] = slot_widgets
            group.setLayout(group_layout)
            scroll_layout.addWidget(group)
        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_content.setStyleSheet(f'background: {BG_HEADER};')
        scroll.setWidget(scroll_content)
        prices_layout.addWidget(scroll)
        save_prices_btn = QPushButton('💾 Nomlar va narxlarni saqlash')
        save_prices_btn.clicked.connect(self.save_prices)
        save_prices_btn.setMinimumHeight(40)
        prices_layout.addWidget(save_prices_btn)
        prices_group.setLayout(prices_layout)
        layout.addWidget(prices_group)
        layout.addStretch()
        combined_widget.setLayout(layout)
        self.tabs.addTab(combined_widget, 'Narxlar')
    def create_password_tab(self):
        """Parolni o\'zgartirish tabi - oxirgi, oq rangda"""
        password_widget = QWidget()
        password_widget.setStyleSheet(f'background: {BG_HEADER};')
        layout = QVBoxLayout()
        title = QLabel('PAROLNI O\'ZGARTIRISH')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'font-size: 24px; font-weight: bold; color: {ACCENT}; margin: 20px;')
        layout.addWidget(title)
        info = QLabel('Bu bo\'limda admin panel parolini o\'zgartirishingiz mumkin')
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(f'font-size: 14px; color: {TEXT_SECONDARY}; margin-bottom: 20px;')
        layout.addWidget(info)
        change_btn = QPushButton('PAROLNI O\'ZGARTIRISH')
        change_btn.setStyleSheet(f'\n            QPushButton {{\n                background: {ACCENT};\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 15px 30px;\n                font-size: 16px;\n            }}\n            QPushButton:hover {{\n                background: #67E8F9;\n                color: #FFFFFF;\n            }}\n        ')
        change_btn.clicked.connect(self.change_password)
        change_btn.setMinimumHeight(50)
        layout.addWidget(change_btn)
        layout.addStretch()
        password_widget.setLayout(layout)
        self.tabs.addTab(password_widget, 'PAROL')
    def create_operator_reports_tab(self):
        """OPERATOR XISOBOT tabi — operatorlar saqlagan smena hisobotlari.\n\n        Yuqorida 4 ta operator tugmasi. Admin operatorni tanlasa, o\'sha\n        operatorning barcha hisobotlari (sanalari bilan) ko\'rsatiladi.\n        Operator nomini taxrirlash va hisobotlarni o\'chirish mumkin.\n        """
        widget = QWidget()
        layout = QVBoxLayout()
        title = QLabel('OPERATOR XISOBOT')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'font-size: 22px; font-weight: bold; color: {ACCENT}; margin: 8px;')
        layout.addWidget(title)
        info = QLabel('Operatorni tanlang — uning barcha hisobotlari ko\'rsatiladi.')
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(f'font-size: 13px; color: {TEXT_SECONDARY}; margin-bottom: 6px;')
        layout.addWidget(info)
        self._selected_operator = None
        self._op_buttons = {}
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for slot in [1, 2, 3, 4]:
            b = QPushButton(db.get_operator_name(slot))
            b.setCheckable(True)
            b.setMinimumHeight(48)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _checked, s=slot: self.select_operator(s))
            self._op_buttons[slot] = b
            btn_row.addWidget(b)
        layout.addLayout(btn_row)
        self._style_operator_buttons()
        head_row = QHBoxLayout()
        self.op_selected_lbl = QLabel('Operator tanlanmagan')
        self.op_selected_lbl.setStyleSheet(f'color: {ACCENT}; font-weight: 800; font-size: 16px;')
        head_row.addWidget(self.op_selected_lbl)
        head_row.addStretch()
        self.op_rename_btn = QPushButton('✏️ Nomini o\'zgartirish')
        self.op_rename_btn.clicked.connect(self.rename_operator)
        self.op_rename_btn.setEnabled(False)
        head_row.addWidget(self.op_rename_btn)
        layout.addLayout(head_row)
        self.op_reports_table = QTableWidget()
        self.op_reports_table.setColumnCount(6)
        self.op_reports_table.setHorizontalHeaderLabels(['Saqlangan sana/vaqt', 'Kassa kuni', 'Jami', 'Seans', 'Ichimlik', 'Market'])
        self.op_reports_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.op_reports_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.op_reports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.op_reports_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.op_reports_table.itemSelectionChanged.connect(self.show_operator_report_detail)
        layout.addWidget(self.op_reports_table)
        det_row = QHBoxLayout()
        detail_lbl = QLabel('Tafsilotlar (kassa smenasi):')
        detail_lbl.setStyleSheet(f'color: {ACCENT}; font-weight: 700; margin-top: 6px;')
        det_row.addWidget(detail_lbl)
        det_row.addStretch()
        self.op_delete_btn = QPushButton('🗑 Hisobotni o\'chirish')
        self.op_delete_btn.setStyleSheet(f'QPushButton {{ background: {COL_RED}; color: #fff; font-weight: 700; border: none; border-radius: 8px; padding: 8px 14px; }}QPushButton:hover {{ background: #FF7A8A; }}')
        self.op_delete_btn.clicked.connect(self.delete_selected_report)
        self.op_delete_btn.setEnabled(False)
        det_row.addWidget(self.op_delete_btn)
        layout.addLayout(det_row)
        self.op_report_detail = QTextEdit()
        self.op_report_detail.setReadOnly(True)
        self.op_report_detail.setMinimumHeight(320)
        layout.addWidget(self.op_report_detail)
        self._op_reports_cache = []
        widget.setLayout(layout)
        self.tabs.addTab(widget, 'OPERATOR XISOBOT')
    def create_telegram_tab(self):
        """Telegram bot sozlamalari — kassa jabıwda 3 ta xabar."""
        from app.services.telegram_notify import get_telegram_config
        widget = QWidget()
        layout = QVBoxLayout()
        title = QLabel('TELEGRAM BOT')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'font-size: 22px; font-weight: bold; color: {ACCENT}; margin: 8px;')
        layout.addWidget(title)
        info = QLabel('<b>🎮 Eagle Playstation bot</b><br><br>1) Telegramda <b>@BotFather</b> ga /newbot yuboring<br>2) Bot nomi: <b>Eagle Playstation</b>, username: masalan <b>eagle_playstation_bot</b><br>3) Berilgan <b>token</b> ni pastdagi maydonga qo\'ying<br>4) Har bir akkountdan botga <b>/start</b> yozing, keyin Chat ID larni oling<br>5) Bir nechta Chat ID ni <b>vergul</b> bilan yozing<br><br>Kassa <b>Saqlaw</b> bosilganda avtomatik 3 ta xabar ketadi:<br>• Smena yakuni (summary)<br>• Smena detallari<br>• Tovar_Otchyot PDF<br><br>Ombor: <b>Ichimliklar / Market → SONI</b> da sonni o\'zgartirib <b>Saqlash</b> bosilganda ham Telegramga xabar ketadi.')
        info.setWordWrap(True)
        info.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px; padding: 8px;')
        layout.addWidget(info)
        form = QFormLayout()
        token, chat = get_telegram_config()
        self.tg_token = QLineEdit(token)
        self.tg_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.tg_token.setPlaceholderText('123456:ABC-DEF...')
        self.tg_chat = QLineEdit(chat)
        self.tg_chat.setPlaceholderText('Masalan: 913795947, 771779619')
        form.addRow('Bot token:', self.tg_token)
        form.addRow('Chat ID (lar):', self.tg_chat)
        layout.addLayout(form)
        self.tg_status = QLabel('')
        self.tg_status.setStyleSheet(f'color: {TEXT_SECONDARY}; font-weight: 700;')
        layout.addWidget(self.tg_status)
        row = QHBoxLayout()
        save_btn = QPushButton('💾 Saqlash')
        save_btn.setMinimumHeight(44)
        save_btn.clicked.connect(self._save_telegram_settings)
        test_btn = QPushButton('📡 Test xabar')
        test_btn.setMinimumHeight(44)
        test_btn.clicked.connect(self._test_telegram)
        show_btn = QPushButton('👁 Tokenni ko\'rsat')
        show_btn.setCheckable(True)
        show_btn.toggled.connect(lambda on: self.tg_token.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        row.addWidget(save_btn)
        row.addWidget(test_btn)
        row.addWidget(show_btn)
        layout.addLayout(row)
        layout.addStretch()
        widget.setLayout(layout)
        self.tabs.addTab(widget, 'TELEGRAM')
    def _save_telegram_settings(self) -> None:
        from app.services.telegram_notify import set_telegram_config
        set_telegram_config(self.tg_token.text(), self.tg_chat.text())
        self.tg_status.setText('Saqlandi.')
        self.tg_status.setStyleSheet(f'color: {COL_GREEN}; font-weight: 800;')
    def _test_telegram(self) -> None:
        from app.services.telegram_notify import set_telegram_config, test_telegram_connection
        import threading
        set_telegram_config(self.tg_token.text(), self.tg_chat.text())
        self.tg_status.setText('Tekshirilmoqda (internet kerak)...')
        self.tg_status.setStyleSheet(f'color: {TEXT_SECONDARY}; font-weight: 800;')
        def _run() -> None:
            result = test_telegram_connection()
            QTimer.singleShot(0, lambda r=result: self._telegram_test_done(r))
        threading.Thread(target=_run, daemon=True, name='tg-test').start()
    def _telegram_test_done(self, result: str) -> None:
        ok = (result or '').startswith('OK')
        self.tg_status.setText(result)
        self.tg_status.setStyleSheet(f'color: {(COL_GREEN if ok else COL_RED)}; font-weight: 800;')
        if ok:
            QMessageBox.information(self, 'Telegram', result)
        else:
            QMessageBox.warning(self, 'Telegram', result)
    def create_zakaz_qr_tab(self):
        """5 ta QR — avtomatik internet tunnel (Google/Telegram shart emas)."""
        from app.services.zakaz_settings import get_public_base_url, get_zakaz_enabled, get_zakaz_port
        widget = QWidget()
        layout = QVBoxLayout()
        title = QLabel('QR ЗАКАЗ')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'font-size: 22px; font-weight: bold; color: {ACCENT}; margin: 8px;')
        layout.addWidget(title)
        info = QLabel('Telefon istalgan Wi‑Fi / internetdan QR → <b>ЗАКАЗ</b>.<br>Har raqam: «Заказ для номера 1…5» + monitor 2 soniya.<br><b>Saqlash</b> bosilganda server + internet tunnel avtomatik ochiladi, QR yangilanadi.')
        info.setWordWrap(True)
        info.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px; padding: 6px;')
        layout.addWidget(info)
        form = QFormLayout()
        self.zakaz_enabled = QCheckBox('QR ЗАКАЗ yoqilgan')
        self.zakaz_enabled.setChecked(get_zakaz_enabled())
        self.zakaz_port = QSpinBox()
        self.zakaz_port.setRange(1024, 65535)
        self.zakaz_port.setValue(get_zakaz_port())
        form.addRow('', self.zakaz_enabled)
        form.addRow('Port:', self.zakaz_port)
        layout.addLayout(form)
        self.zakaz_url_lbl = QLabel(get_public_base_url() or 'Hali tunnel yo\'q — Saqlash ni bosing')
        self.zakaz_url_lbl.setWordWrap(True)
        self.zakaz_url_lbl.setStyleSheet(f'color: {ACCENT}; font-weight: 700;')
        layout.addWidget(self.zakaz_url_lbl)
        self.zakaz_status = QLabel('')
        self.zakaz_status.setStyleSheet(f'color: {TEXT_SECONDARY}; font-weight: 700;')
        layout.addWidget(self.zakaz_status)
        qr_grid = QGridLayout()
        qr_grid.setSpacing(12)
        self._zakaz_qr_labels = {}
        self._zakaz_url_labels = {}
        for n in range(1, 6):
            box = QVBoxLayout()
            cap = QLabel(f'QR #{n}')
            cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap.setStyleSheet('font-weight: 800;')
            img = QLabel()
            img.setFixedSize(140, 140)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img.setStyleSheet(f'background: #fff; border: 1px solid {BORDER}; border-radius: 8px;')
            url_l = QLabel('')
            url_l.setWordWrap(True)
            url_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            url_l.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 10px;')
            test_btn = QPushButton(f'Test {n}')
            test_btn.setMinimumHeight(32)
            test_btn.clicked.connect(lambda _=False, num=n: self._test_zakaz(num))
            box.addWidget(cap)
            box.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(url_l)
            box.addWidget(test_btn)
            cell = QWidget()
            cell.setLayout(box)
            qr_grid.addWidget(cell, 0, n - 1)
            self._zakaz_qr_labels[n] = img
            self._zakaz_url_labels[n] = url_l
        layout.addLayout(qr_grid)
        row = QHBoxLayout()
        save_btn = QPushButton('💾 Saqlash / QR yangilash')
        save_btn.setMinimumHeight(44)
        save_btn.clicked.connect(self._save_zakaz_settings)
        export_btn = QPushButton('📁 PNG saqlash')
        export_btn.setMinimumHeight(44)
        export_btn.clicked.connect(self._export_zakaz_qrs)
        row.addWidget(save_btn)
        row.addWidget(export_btn)
        layout.addLayout(row)
        layout.addStretch()
        widget.setLayout(layout)
        self.tabs.addTab(widget, 'QR ZAKAZ')
        self._refresh_zakaz_qrs()
    def _zakaz_urls(self) -> tuple[str, list[str]]:
        from app.services.zakaz_settings import get_public_base_url, get_zakaz_port, zakaz_page_url
        from app.services.zakaz_server import base_url
        port = int(self.zakaz_port.value()) if hasattr(self, 'zakaz_port') else get_zakaz_port()
        public = get_public_base_url()
        base = public or base_url(port)
        urls = [zakaz_page_url(n, base=public or None, port=port) for n in range(1, 6)]
        return (base, urls)
    def _refresh_zakaz_qrs(self) -> None:
        from app.services.zakaz_server import make_qr_png
        from app.services.zakaz_settings import get_public_base_url
        base, urls = self._zakaz_urls()
        pub = get_public_base_url()
        self.zakaz_url_lbl.setText(f'Internet: {pub}' if pub else f'Lokal (bir Wi‑Fi): {base}')
        for n, url in enumerate(urls, start=1):
            self._zakaz_url_labels[n].setText(url)
            try:
                png = make_qr_png(url, box_size=6)
                pix = QPixmap()
                pix.loadFromData(png)
                self._zakaz_qr_labels[n].setPixmap(pix.scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except Exception as e:
                self._zakaz_qr_labels[n].setText('QR?')
                self.zakaz_status.setText(f'QR xato: {e}')
                self.zakaz_status.setStyleSheet(f'color: {COL_RED}; font-weight: 800;')
    def _save_zakaz_settings(self) -> None:
        from app.services.zakaz_settings import set_zakaz_enabled, set_zakaz_port
        set_zakaz_enabled(self.zakaz_enabled.isChecked())
        set_zakaz_port(self.zakaz_port.value())
        parent = self.parent()
        ok = False
        err = ''
        if parent is not None and hasattr(parent, 'restart_zakaz_server'):
            try:
                ok, err = parent.restart_zakaz_server()
            except Exception as e:
                ok, err = (False, str(e))
        else:
            ok, err = (True, 'Sozlama saqlandi.')
        self._refresh_zakaz_qrs()
        try:
            self._export_zakaz_qrs(auto_path=True)
        except Exception:
            pass
        if ok:
            self.zakaz_status.setText(err or 'Saqlandi.')
            self.zakaz_status.setStyleSheet(f'color: {COL_GREEN}; font-weight: 800;')
            QMessageBox.information(self, 'QR ЗАКАЗ', self.zakaz_status.text())
        else:
            self.zakaz_status.setText(err or 'Ishga tushmadi.')
            self.zakaz_status.setStyleSheet(f'color: {COL_RED}; font-weight: 800;')
            QMessageBox.warning(self, 'QR ЗАКАЗ', self.zakaz_status.text())
    def _test_zakaz(self, n: int) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, 'trigger_zakaz'):
            parent.trigger_zakaz(int(n))
            self.zakaz_status.setText(f'Test #{n}: «Заказ для номера {n}»')
            self.zakaz_status.setStyleSheet(f'color: {COL_GREEN}; font-weight: 800;')
        else:
            QMessageBox.warning(self, 'QR ЗАКАЗ', 'Asosiy oynadan oching.')
    def _export_zakaz_qrs(self, auto_path: bool=False) -> None:
        from app.core.paths import application_dir
        from app.services.zakaz_qr_export import make_qr_sheet_png
        from app.services.zakaz_server import make_qr_png
        base, urls = self._zakaz_urls()
        if not urls:
            return
        else:
            if auto_path:
                path = application_dir() / 'ZAKAZ_QR_5.png'
            else:
                folder = QFileDialog.getExistingDirectory(self, 'PNG saqlash papkasi')
                if not folder:
                    return
                else:
                    path = Path(folder) / 'ZAKAZ_QR_5.png'
        try:
            make_qr_sheet_png(urls, labels=[f'ЗАКАЗ #{n}' for n in range(1, 6)], out_path=path)
            for n, url in enumerate(urls, start=1):
                (path.parent / f'zakaz_qr_{n}.png').write_bytes(make_qr_png(url, box_size=10))
            if not auto_path:
                QMessageBox.information(self, 'QR ЗАКАЗ', f'Saqlandi:\n{path}')
            else:
                self.zakaz_status.setText(f'PNG: {path}')
        except Exception as e:
            if not auto_path:
                QMessageBox.warning(self, 'QR ЗАКАЗ', f'Saqlash xato: {e}')
    def _style_operator_buttons(self):
        """Operator tugmalari ko\'rinishi (tanlangani ajralib turadi)."""
        for slot, b in self._op_buttons.items():
            if b.isChecked():
                b.setStyleSheet(f'QPushButton {{ background: {ACCENT}; color: #FFFFFF; font-weight: 900; border: none; border-radius: 10px; font-size: 15px; }}}}')
            else:
                b.setStyleSheet(f'QPushButton {{ background: {BG_CARD}; color: {TEXT_PRIMARY}; font-weight: 700; border: 1px solid {BORDER}; border-radius: 10px; font-size: 15px; }}QPushButton:hover {{ border: 1px solid {ACCENT}; }}')
    def select_operator(self, slot: int):
        """Operatorni tanlash va hisobotlarini yuklash."""
        self._selected_operator = slot
        for s, b in self._op_buttons.items():
            b.setChecked(s == slot)
        self._style_operator_buttons()
        name = db.get_operator_name(slot)
        self.op_selected_lbl.setText(f'📋 {name} — barcha hisobotlar')
        self.op_rename_btn.setEnabled(True)
        self.load_operator_reports()
    def rename_operator(self):
        """Tanlangan operator nomini o\'zgartirish (masalan 2-operator = Amir)."""
        slot = self._selected_operator
        if slot is None:
            return
        else:
            current = db.get_operator_name(slot)
            new_name, ok = QInputDialog.getText(self, 'Operator nomi', f'{slot}-operator uchun yangi nom:', QLineEdit.EchoMode.Normal, current)
            if not ok:
                return
            else:
                new_name = new_name.strip()
                db.set_operator_name(slot, new_name)
                display = db.get_operator_name(slot)
                self._op_buttons[slot].setText(display)
                self.op_selected_lbl.setText(f'📋 {display} — barcha hisobotlar')
    def load_operator_reports(self):
        """Tanlangan operatorning saqlangan hisobotlarini yuklash."""
        slot = self._selected_operator
        if slot is None:
            return
        else:
            try:
                reports = db.get_operator_reports(slot)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Hisobotlarni yuklashda xatolik:\n{e}')
                return None
            self._op_reports_cache = reports
            self.op_reports_table.setRowCount(len(reports))
            for i, r in enumerate(reports):
                self.op_reports_table.setItem(i, 0, QTableWidgetItem(self._fmt_dt(r.get('saved_time', ''))))
                self.op_reports_table.setItem(i, 1, QTableWidgetItem(str(r.get('business_day', ''))))
                self.op_reports_table.setItem(i, 2, QTableWidgetItem(f"{float(r.get('total_revenue', 0)):,.0f}"))
                self.op_reports_table.setItem(i, 3, QTableWidgetItem(f"{float(r.get('session_revenue', 0)):,.0f}"))
                self.op_reports_table.setItem(i, 4, QTableWidgetItem(f"{float(r.get('drink_revenue', 0)):,.0f}"))
                self.op_reports_table.setItem(i, 5, QTableWidgetItem(f"{float(r.get('market_revenue', 0)):,.0f}"))
            self.op_report_detail.clear()
            self.op_delete_btn.setEnabled(False)
            if reports:
                self.op_reports_table.selectRow(0)
            else:
                self.op_report_detail.setPlainText('Bu operator hali hisobot saqlamagan.')
    def delete_selected_report(self):
        """Tanlangan hisobotni o\'chirish."""
        row = self.op_reports_table.currentRow()
        if row < 0 or row >= len(self._op_reports_cache):
            return None
        else:
            r = self._op_reports_cache[row]
            confirm = QMessageBox.question(self, 'O\'chirish', f"{self._fmt_dt(r.get('saved_time', ''))} dagi hisobot o\'chirilsinmi?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm != QMessageBox.StandardButton.Yes:
                return
            else:
                try:
                    db.delete_operator_report(int(r.get('id')))
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', f'O\'chirishda xatolik:\n{e}')
                    return None
                self.load_operator_reports()
    def show_operator_report_detail(self):
        """Tanlangan hisobot tafsilotlarini ko'rsatish (2-rasm formati)."""
        row = self.op_reports_table.currentRow()
        if row < 0 or row >= len(self._op_reports_cache):
            self.op_delete_btn.setEnabled(False)
            return
        self.op_delete_btn.setEnabled(True)
        r = self._op_reports_cache[row]
        text = str(r.get('summary_text') or '').strip()
        if not text:
            from app.services.shift_report import format_shift_summary
            snap = {'operator_name': r.get('operator_name') or db.get_operator_name(int(r.get('operator_index') or 0)),
                'period_start': r.get('period_start'),
                'period_end': r.get('period_end') or r.get('saved_time'),
                'saved_time': r.get('saved_time'),
                'session_total': float(r.get('session_total') or r.get('session_revenue') or 0),
                'joystick_total': float(r.get('joystick_total') or r.get('joystick_revenue') or 0),
                'goods_total': float(r.get('goods_total') or 0) or float(r.get('drink_revenue') or 0) + float(r.get('market_revenue') or 0),
                'goods_profit': float(r.get('goods_profit') or 0),
                'client_count': int(r.get('client_count') or 0),
                'avg_payment': float(r.get('avg_payment') or 0),
                'expense_total': float(r.get('expense_total') or 0),
                'debt_total': float(r.get('debt_total') or 0),
                'debt_paid_total': float(r.get('debt_paid_total') or 0),
                'total': float(r.get('total') or r.get('total_revenue') or 0),
                'net_profit': float(r.get('net_profit') or 0),
                'closing_amount': float(r.get('closing_amount') or 0),
                'expected_amount': float(r.get('expected_amount') or 0),
                'cash_diff': float(r.get('cash_diff') or 0),
                'click_total': float(r.get('click_total') or 0)}
            if not snap['avg_payment'] and snap['client_count']:
                snap['avg_payment'] = snap['total'] / snap['client_count']
            if not snap['expected_amount'] and snap['total']:
                snap['expected_amount'] = snap['total'] + snap['debt_paid_total'] - snap['expense_total'] - snap['debt_total']
                snap['cash_diff'] = snap['closing_amount'] + snap['click_total'] - snap['expected_amount']
            elif not snap['cash_diff'] and snap['expected_amount']:
                snap['cash_diff'] = snap['closing_amount'] + snap['click_total'] - snap['expected_amount']
            if not snap['net_profit']:
                snap['net_profit'] = snap['session_total'] + snap['joystick_total'] + snap['goods_profit'] - snap['expense_total']
            text = format_shift_summary(snap)
        self.op_report_detail.setPlainText(text)
    @staticmethod
    def _fmt_dt(value: str) -> str:
        if not value:
            return ''
        else:
            text = str(value)
            if 'T' in text:
                d, t = text.split('T', 1)
                return f'{d} {t[:5]}'
            else:
                return text[:16]
    def create_daily_report_tab(self):
        """Kunlik hisobot tabini yaratish"""
        report_widget = QWidget()
        layout = QVBoxLayout()
        date_group = QGroupBox('Sana tanlash')
        date_layout = QHBoxLayout()
        self.report_date = QDateEdit()
        self.report_date.setCalendarPopup(True)
        self.report_date.setDisplayFormat('dd.MM.yyyy')
        self.report_date.setMinimumDate(QDate.currentDate().addMonths((-1)))
        self.report_date.setMaximumDate(QDate.currentDate())
        biz = db.current_business_date()
        self.report_date.setDate(QDate(biz.year, biz.month, biz.day))
        self.report_date.dateChanged.connect(self.update_daily_report)
        date_layout.addWidget(self.report_date)
        date_layout.addStretch()
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        revenue_group = QGroupBox('Kunlik daromad')
        revenue_layout = QVBoxLayout()
        self.total_revenue_label = QLabel('Jami daromad: 0 so\'m')
        self.total_revenue_label.setStyleSheet(f'font-size: 24px; font-weight: 900; color: {COL_GREEN};')
        self.session_revenue_label = QLabel('Seanslardan: 0 so\'m')
        self.session_revenue_label.setStyleSheet(f'font-size: 16px; color: {TEXT_PRIMARY};')
        self.market_revenue_label = QLabel('Ichimliklardan: 0 so\'m')
        self.market_revenue_label.setStyleSheet(f'font-size: 16px; color: {TEXT_PRIMARY};')
        revenue_layout.addWidget(self.total_revenue_label)
        revenue_layout.addWidget(self.session_revenue_label)
        revenue_layout.addWidget(self.market_revenue_label)
        revenue_group.setLayout(revenue_layout)
        layout.addWidget(revenue_group)
        sessions_group = QGroupBox('SEANLAR RO\'YXATI')
        sessions_layout = QVBoxLayout()
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(7)
        self.sessions_table.setHorizontalHeaderLabels(['Stol', 'Boshlangan', 'Tugatilgan', 'Daqiqa', 'Seans (so\'m)', 'Ichimlik (so\'m)', 'Jami (so\'m)'])
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sessions_table.setStyleSheet(f'\n            QTableWidget {{ background: {BG_CARD}; color: {TEXT_PRIMARY}; gridline-color: {BORDER}; border: none; }}\n            QHeaderView::section {{ background: {BG_HEADER}; color: {ACCENT}; padding: 8px; font-weight: 800; border: 1px solid {BORDER}; }}\n            QTableWidget::item {{ padding: 6px; color: {TEXT_PRIMARY}; }}\n            ')
        sessions_layout.addWidget(self.sessions_table)
        sessions_group.setLayout(sessions_layout)
        layout.addWidget(sessions_group)
        refresh_btn = QPushButton('🔄 Hisobotni yangilash')
        refresh_btn.clicked.connect(self.update_daily_report)
        refresh_btn.setMinimumHeight(40)
        layout.addWidget(refresh_btn)
        layout.addStretch()
        report_widget.setLayout(layout)
        self.tabs.addTab(report_widget, 'Kunlik hisobot')
        self.update_daily_report()
    def create_day_settings_tab(self):
        """Biznes kuni boshlanish vaqtini sozlash (KUN tabi)."""
        widget = QWidget()
        layout = QVBoxLayout()
        info = QLabel('<b>Kun qachon boshlanishini belgilang.</b><br><br>Masalan, <b>06:00</b> tanlansa — soat 06:00 dan keyingi kun <b>ertasi kuni 05:59</b> gacha bir kun hisoblanadi.<br><br>Kechasi 00:00 dan o\'tganda ham kassa yopilmaguncha (masalan soat 02:00–03:00 gacha) daromad shu kunga qo\'shiladi.')
        info.setWordWrap(True)
        info.setStyleSheet(f'font-size: 14px; color: {TEXT_SECONDARY}; padding: 8px;')
        layout.addWidget(info)
        time_group = QGroupBox('Kun boshlanish vaqti')
        time_layout = QFormLayout()
        self.day_start_time = QTimeEdit()
        self.day_start_time.setDisplayFormat('HH:mm')
        self.day_start_time.setMinimumTime(QTime(0, 0))
        self.day_start_time.setMaximumTime(QTime(23, 59))
        h, m = db.get_business_day_start()
        self.day_start_time.setTime(QTime(h, m))
        self.day_range_label = QLabel()
        self.day_range_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
        self._update_day_range_preview()
        self.day_start_time.timeChanged.connect(self._update_day_range_preview)
        time_layout.addRow('Yangi kun boshlanadi:', self.day_start_time)
        time_layout.addRow('', self.day_range_label)
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)
        save_btn = QPushButton('💾 Kun sozlamasini saqlash')
        save_btn.setMinimumHeight(50)
        save_btn.clicked.connect(self.save_day_settings)
        layout.addWidget(save_btn)
        layout.addStretch()
        widget.setLayout(layout)
        self.tabs.addTab(widget, 'KUN')
    def _update_day_range_preview(self) -> None:
        t = self.day_start_time.time()
        hh, mm = (t.hour(), t.minute())
        end_h, end_m = (hh, mm - 1)
        if end_m < 0:
            end_m = 59
            end_h = (end_h - 1) % 24
        self.day_range_label.setText(f'Har bir kun: <b>{hh:02d}:{mm:02d}</b> dan — ertasi kuni <b>{end_h:02d}:{end_m:02d}</b> gacha')
    def save_day_settings(self) -> None:
        t = self.day_start_time.time()
        db.set_business_day_start(t.hour(), t.minute())
        QMessageBox.information(self, 'Saqlandi', f"Kun boshlanish vaqti: {t.toString('HH:mm')}\n\nBugungi daromad va kunlik hisobot endi shu vaqt bo\'yicha hisoblanadi.")
        self.update_daily_report()
    def create_license_tab(self):
        """Litsenziya muddati (MUDDAT) tabi."""
        widget = QWidget()
        layout = QVBoxLayout()
        self._lic_days_big = QLabel()
        self._lic_days_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lic_days_big.setStyleSheet(f'font-size: 52px; font-weight: 900; color: {ACCENT}; padding: 4px;')
        layout.addWidget(self._lic_days_big)
        self._lic_days_caption = QLabel('qolgan kun')
        self._lic_days_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lic_days_caption.setStyleSheet(f'font-size: 14px; color: {TEXT_SECONDARY};')
        layout.addWidget(self._lic_days_caption)
        self._lic_warning = QLabel()
        self._lic_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lic_warning.setWordWrap(True)
        self._lic_warning.hide()
        layout.addWidget(self._lic_warning)
        info_group = QGroupBox('Litsenziya ma\'lumotlari')
        form = QFormLayout()
        self._lic_state_label = QLabel('-')
        self._lic_type_label = QLabel('-')
        self._lic_expiry_label = QLabel('-')
        self._lic_days_label = QLabel('-')
        self._lic_renew_label = QLabel('-')
        self._lic_time_label = QLabel('-')
        self._lic_source_label = QLabel('-')
        self._lic_hwid_label = QLabel('-')
        self._lic_hwid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._lic_hwid_label.setWordWrap(True)
        form.addRow('Holat:', self._lic_state_label)
        form.addRow('Turi:', self._lic_type_label)
        form.addRow('Tugash sanasi:', self._lic_expiry_label)
        form.addRow('Qolgan kun:', self._lic_days_label)
        form.addRow('Yangilanish:', self._lic_renew_label)
        form.addRow('Hozirgi vaqt (UZ):', self._lic_time_label)
        form.addRow('Vaqt manbasi:', self._lic_source_label)
        form.addRow('Kompyuter kodi (HWID):', self._lic_hwid_label)
        info_group.setLayout(form)
        layout.addWidget(info_group)
        btn_row = QHBoxLayout()
        copy_btn = QPushButton('HWID nusxalash')
        copy_btn.clicked.connect(self._copy_hwid_to_clipboard)
        refresh_btn = QPushButton('Yangilash')
        refresh_btn.clicked.connect(self._refresh_license_tab)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        note = QLabel('Oylik litsenziya har oyning 10-sanada tugaydi.\nMuddat tugashidan oldin dasturchiga HWID yuborib yangi license.key oling.')
        note.setWordWrap(True)
        note.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px; padding: 8px;')
        layout.addWidget(note)
        layout.addStretch()
        widget.setLayout(layout)
        self.tabs.addTab(widget, 'MUDDAT')
        self._refresh_license_tab()
    def _copy_hwid_to_clipboard(self) -> None:
        text = self._lic_hwid_label.text().strip()
        if not text or text != '-':
                QGuiApplication.clipboard().setText(text)
                QMessageBox.information(self, 'Nusxalandi', 'HWID vaqtinchalik xotiraga nusxalandi.')
    def _refresh_license_tab(self) -> None:
        try:
            from app.auth import license_manager
            st = license_manager.get_license_status()
            self._lic_state_label.setText(st.status_text)
            self._lic_hwid_label.setText(st.hwid)
            self._lic_time_label.setText(st.current_time)
            self._lic_source_label.setText(st.time_source)
            self._lic_renew_label.setText(f'Har oyning {st.monthly_renew_day}-sanada')
            if st.lic_type == 'PERMANENT':
                self._lic_type_label.setText('Doimiy (PERMANENT)')
                self._lic_expiry_label.setText('Cheksiz')
                self._lic_days_label.setText('—')
                self._lic_days_big.setText('∞')
                self._lic_days_caption.setText('doimiy litsenziya')
                self._lic_days_big.setStyleSheet('font-size: 52px; font-weight: 900; color: #00C853; padding: 4px;')
                self._lic_warning.hide()
            else:
                if st.lic_type == 'MONTHLY' and st.expiry is not None:
                    self._lic_type_label.setText('Oylik (MONTHLY)')
                    self._lic_expiry_label.setText(st.expiry.strftime('%d.%m.%Y'))
                    days = st.days_left if st.days_left is not None else 0
                    self._lic_days_label.setText(f'{days} kun')
                    self._lic_days_big.setText(f'{days}')
                    self._lic_days_caption.setText('qolgan kun')
                    if st.show_expiry_warning:
                        color = '#D50000'
                        self._lic_days_big.setStyleSheet(f'font-size: 52px; font-weight: 900; color: {color}; padding: 4px;')
                        self._lic_state_label.setStyleSheet('color: #D50000; font-weight: bold;')
                        self._lic_warning.setText('DIQQAT! Litsenziya 1 kun qoldi!\nDasturchiga HWID yuborib yangi license.key oling.')
                        self._lic_warning.setStyleSheet('background: #FFEBEE; color: #B71C1C; font-weight: bold; font-size: 15px; padding: 12px; border-radius: 8px; border: 2px solid #EF5350;')
                        self._lic_warning.show()
                    else:
                        if days <= 3:
                            self._lic_days_big.setStyleSheet('font-size: 52px; font-weight: 900; color: #FF8F00; padding: 4px;')
                            self._lic_state_label.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: bold;')
                            self._lic_warning.hide()
                        else:
                            self._lic_days_big.setStyleSheet(f'font-size: 52px; font-weight: 900; color: {ACCENT}; padding: 4px;')
                            self._lic_state_label.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: bold;')
                            self._lic_warning.hide()
                else:
                    self._lic_type_label.setText(st.lic_type or 'Noma\'lum')
                    self._lic_expiry_label.setText('—')
                    self._lic_days_label.setText('—')
                    self._lic_days_big.setText('—')
                    self._lic_days_caption.setText('')
                    self._lic_state_label.setStyleSheet(f'color: {TEXT_PRIMARY};')
                    self._lic_warning.hide()
        except Exception as e:
            print(f'MUDDAT yangilashda xatolik: {e}')
    def update_daily_report(self):
        """Kunlik hisobotni yangilash"""
        try:
            selected_date = self.report_date.date().toString('yyyy-MM-dd')
            split = db.revenue_split_for_day(selected_date)
            total = split['total']
            sessions = db.sessions_breakdown_for_day(selected_date)
            self.sessions_table.setRowCount(len(sessions))
            session_total = 0.0
            drink_total = 0.0
            for i, s in enumerate(sessions):
                station_id = s.get('station_id', '')
                start = self._format_time_only(s.get('start_time', ''))
                end = self._format_time_only(s.get('end_time', ''))
                minutes = int(s.get('duration_minutes') or 0)
                ses_rev = float(s.get('session_revenue') or 0) + float(s.get('joystick_revenue') or 0)
                dri_rev = float(s.get('drink_revenue') or 0)
                tot_rev = float(s.get('revenue') or 0)
                self.sessions_table.setItem(i, 0, QTableWidgetItem(db.get_station_display_name(station_id)))
                self.sessions_table.setItem(i, 1, QTableWidgetItem(start))
                self.sessions_table.setItem(i, 2, QTableWidgetItem(end))
                self.sessions_table.setItem(i, 3, QTableWidgetItem(str(minutes)))
                self.sessions_table.setItem(i, 4, QTableWidgetItem(f'{ses_rev:,.0f}'))
                self.sessions_table.setItem(i, 5, QTableWidgetItem(f'{dri_rev:,.0f}'))
                self.sessions_table.setItem(i, 6, QTableWidgetItem(f'{tot_rev:,.0f}'))
                session_total += ses_rev
                drink_total += dri_rev
            self.total_revenue_label.setText(f'Jami daromad: {total:,.0f} so\'m')
            self.session_revenue_label.setText(f"Seanslardan: {split['session_total']:,.0f} so\'m")
            self.market_revenue_label.setText(f"Ichimliklardan: {split['drink_total']:,.0f} so\'m")
        except Exception as e:
            print(f'Hisobot yangilashda xatolik: {e}')
    @staticmethod
    def _format_time_only(value: str) -> str:
        """ISO datetime qiymatidan faqat HH:MM qismini chiqaradi."""
        if not value:
            return ''
        else:
            text = str(value)
            if 'T' in text:
                return text.split('T', 1)[1][:5]
            else:
                if ' ' in text:
                    return text.split(' ', 1)[1][:5]
                else:
                    return text[:5]
    def save_prices(self):
        """Stol nomlari va narxlarni saqlash"""
        try:
            for station_id, price_input in self.price_inputs.items():
                display_name = self.name_inputs[station_id].text()
                db.set_station_price_and_name(station_id, price_input.value(), display_name)
                slots = []
                for start_time, end_time, slot_price in self.price_slot_inputs.get(station_id, []):
                    start_qt = start_time.time()
                    end_qt = end_time.time()
                    slots.append({'start_minute': start_qt.hour() * 60 + start_qt.minute(), 'end_minute': end_qt.hour() * 60 + end_qt.minute(), 'hourly_rate': slot_price.value()})
                db.set_station_price_slots(station_id, slots)
            self.station_settings_changed.emit()
            QMessageBox.information(self, 'Muvaffaqiyatli', 'Barcha stol nomlari, narxlar va vaqtli tariflar saqlandi!')
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Narxlarni saqlashda xatolik: {str(e)}')
    def save_station_count(self):
        """Stollar sonini saqlash"""
        try:
            new_count = self.station_count.value()
            db.update_station_count(new_count)
            self.station_count_changed.emit(new_count)
            QMessageBox.information(self, 'Muvaffaqiyatli', f'Stollar soni {new_count} ga o\'zgartirildi!')
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Stollar sonini saqlashda xatolik: {str(e)}')
    def save_joystick_price(self):
        """Jostik narxini saqlash"""
        try:
            price = int(self.joystick_price.value())
            db.set_joystick_price(price)
            QMessageBox.information(self, 'Muvaffaqiyatli', f'Jostik narxi {price:,} so\'m/soat qilib saqlandi.\nQo\'shimcha jostik to\'lovi o\'ynagan vaqt bo\'yicha hisoblanadi.')
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Jostik narxini saqlashda xatolik: {str(e)}')
    def change_password(self):
        """Parol o\'zgartirish dialogi"""
        dialog = ChangePasswordDialog('', self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, 'Muvaffaqiyatli', 'Parol muvaffaqiyatli o\'zgartirildi!')