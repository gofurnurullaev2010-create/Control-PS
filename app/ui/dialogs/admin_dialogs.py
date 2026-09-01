from __future__ import annotations
import logging
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
import database as db
from pathlib import Path
import sys
from app.ui.dialogs.colors import ACCENT, ACCENT_HOVER, BG_CARD, BG_HEADER, BG_MAIN, BORDER_COLOR, COL_BLUE, COL_GREEN, COL_RED, GOLD_COLOR, STATUS_FREE, TEXT_PRIMARY, TEXT_SECONDARY
logger = logging.getLogger(__name__)
def _resource_path(filename: str) -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / filename
    else:
        return Path(__file__).resolve().parents[3] / filename
class PasswordDialog(QDialog):
    """Admin panel uchun parol so\'rash oynasi."""
    def __init__(self, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Xavfsizlik')
        self.setFixedSize(300, 150)
        self.setStyleSheet(f'background-color: {BG_MAIN}; color: {TEXT_PRIMARY};')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Admin parolini kiriting:'))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(f'background-color: #FFFFFF; border: 1px solid {ACCENT}; padding: 8px; border-radius: 5px;')
        layout.addWidget(self.password_input)
        self.btn_login = QPushButton('KIRISH')
        self.btn_login.clicked.connect(self.accept)
        layout.addWidget(self.btn_login)
    def get_password(self) -> str:
        return self.password_input.text()
class AdminDialog(QDialog):
    """Admin boshqaruv paneli: sozlamalar va kunlik hisobot."""
    def __init__(self, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Admin Panel - Boshqaruv')
        self.setMinimumWidth(850)
        self.setMinimumHeight(650)
        self.setStyleSheet(f'background-color: {BG_MAIN}; color: {TEXT_PRIMARY};')
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet('\n            QTabWidget::pane { border: 1px solid #CCCCCC; background: #FFFFFF; border-radius: 10px; }\n            QTabBar::tab { background: #F5F5F5; color: #555555; padding: 12px 30px; margin-right: 5px; border-top-left-radius: 8px; border-top-right-radius: 8px; }\n            QTabBar::tab:selected { background: #FFFFFF; color: #111111; font-weight: bold; border-bottom: 2px solid #111111; }\n        ')
        tab_settings = QWidget()
        set_lay = QVBoxLayout(tab_settings)
        count_group = QFrame()
        count_group.setStyleSheet('background-color: #F5F5F5; border-radius: 10px; padding: 15px; border: 1px solid #CCCCCC;')
        count_lay = QHBoxLayout(count_group)
        count_lay.addWidget(QLabel('<b>Stollar jami soni:</b>'))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 100)
        self.spin_count.setValue(db.get_station_count())
        self.spin_count.setStyleSheet(f'background-color: #FFFFFF; color: {ACCENT}; border: 1px solid {ACCENT}; padding: 5px;')
        count_lay.addWidget(self.spin_count)
        set_lay.addWidget(count_group)
        set_lay.addWidget(QLabel('<br><b>Har bir stol uchun soatlik narx:</b>'))
        self.price_table = QTableWidget()
        self.price_table.setColumnCount(2)
        self.price_table.setHorizontalHeaderLabels(['Stol nomi', 'Soatlik narxi (so\'m)'])
        self.price_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.price_table.setStyleSheet('QTableWidget { background: #FFFFFF; } QHeaderView::section { background: #F5F5F5; color: #1A1A1A; font-weight: bold; }')
        self.load_station_prices()
        set_lay.addWidget(self.price_table)
        self.btn_save = QPushButton('💾 BARCHA O\'ZGARISHLARNI SAQLASH')
        self.btn_save.setStyleSheet(f'background-color: {STATUS_FREE}; color: #000; font-weight: bold; padding: 12px; border-radius: 8px;')
        self.btn_save.clicked.connect(self.save_all)
        set_lay.addWidget(self.btn_save)
        tab_report = QWidget()
        rep_lay = QVBoxLayout(tab_report)
        rep_header = QHBoxLayout()
        rep_header.addWidget(QLabel('<b>Bugun yakunlangan seanslar:</b>'))
        btn_refresh = QPushButton('🔄 YANGILASH')
        btn_refresh.setFixedWidth(120)
        btn_refresh.setStyleSheet('background-color: #37474F; color: white; padding: 5px;')
        btn_refresh.clicked.connect(self.load_detailed_report)
        rep_header.addStretch()
        rep_header.addWidget(btn_refresh)
        rep_lay.addLayout(rep_header)
        self.report_table = QTableWidget()
        self.report_table.setColumnCount(5)
        self.report_table.setHorizontalHeaderLabels(['Stol', 'Vaqt', 'Davomiyligi', 'Ichimliklar', 'Jami (so\'m)'])
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_table.setStyleSheet('QTableWidget { background: #FFFFFF; } QHeaderView::section { background: #F5F5F5; color: #1A1A1A; font-weight: bold; }')
        rep_lay.addWidget(self.report_table)
        self.load_detailed_report()
        self.tabs.addTab(tab_settings, '⚙️ SOZLAMALAR')
        self.tabs.addTab(tab_report, '📊 KUNLIK HISOBOT')
        main_layout.addWidget(self.tabs)
    def load_detailed_report(self):
        rows = db.get_detailed_daily_report()
        self.report_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.report_table.setItem(i, 0, QTableWidgetItem(r['station_id']))
            s_time = r['start_time'].split('T')[(-1)][:5] if 'T' in r['start_time'] else r['start_time']
            e_time = r['end_time'].split('T')[(-1)][:5] if 'T' in (r['end_time'] or '') else r['end_time'] or ''
            self.report_table.setItem(i, 1, QTableWidgetItem(f'{s_time} - {e_time}'))
            self.report_table.setItem(i, 2, QTableWidgetItem(f"{r['duration_minutes']} min"))
            self.report_table.setItem(i, 3, QTableWidgetItem(r['drinks'] or '-'))
            rev_item = QTableWidgetItem(f"{r['revenue']:,.0f}")
            rev_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rev_item.setForeground(QColor('#111111'))
            self.report_table.setItem(i, 4, rev_item)
        self.report_table.resizeRowsToContents()
    def load_station_prices(self):
        ids = db.list_station_ids()
        self.price_table.setRowCount(len(ids))
        for i, sid in enumerate(ids):
            self.price_table.setItem(i, 0, QTableWidgetItem(sid))
            price = db.get_station_price(sid)
            price_item = QTableWidgetItem(str(int(price)))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.price_table.setItem(i, 1, price_item)
    def save_all(self):
        try:
            new_count = self.spin_count.value()
            db.update_station_count(new_count)
            for i in range(self.price_table.rowCount()):
                sid = self.price_table.item(i, 0).text()
                try:
                    price = float(self.price_table.item(i, 1).text())
                    db.set_station_price(sid, price)
                except:
                    pass
            QMessageBox.information(self, 'OK', 'Barcha o\'zgarishlar muvaffaqiyatli saqlandi!')
            main = self.parent()
            if hasattr(main, 'refresh_all_cards'):
                main.refresh_all_cards()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
class PasswordChangeDialog(QDialog):
    """Dasturga kirish parolini o\'zgartirish oynasi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('PAROL - Kirish parolini o\'zgartirish')
        self.setFixedSize(450, 400)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        logo_path = _resource_path('ps_logo.png')
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setStyleSheet('\n            QDialog {\n                background: #FFFFFF;\n                color: #1A1A1A;\n                border-radius: 15px;\n            }\n            QLineEdit {\n                background-color: #FFFFFF;\n                border: 1px solid #CFCFCF;\n                border-radius: 10px;\n                padding: 12px;\n                font-size: 16px;\n                color: #111111;\n                font-weight: 600;\n                min-width: 250px;\n            }\n            QLineEdit:focus {\n                border-color: #111111;\n                background-color: #F7F7F7;\n            }\n            QPushButton {\n                background: #111111;\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 15px 30px;\n                font-size: 16px;\n                font-weight: 700;\n            }\n            QPushButton:hover {\n                background: #333333;\n            }\n            QPushButton:pressed {\n                background: #000000;\n            }\n            QLabel {\n                color: #111111;\n                font-size: 16px;\n                font-weight: 700;\n            }\n        ')
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        title = QLabel('🔐 PAROLNI O\'ZGARTIRISH')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet('color: #111111; font-size: 20px; font-weight: bold;')
        layout.addWidget(title)
        info = QLabel('Eski parolingizni kiriting — qaysi operatorga tegishli bo\'lsa, o\'shaning kirish paroli yangilanadi.')
        info.setWordWrap(True)
        info.setStyleSheet('color: #555555; font-size: 12px; font-weight: 500;')
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
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
        self.error_label.setStyleSheet('color: #FF4757; font-weight: bold; font-size: 14px;')
        layout.addWidget(self.error_label)
        button_layout = QHBoxLayout()
        save_btn = QPushButton('🔒 ALMASHTIRISH')
        save_btn.clicked.connect(self._save_password)
        button_layout.addWidget(save_btn)
        cancel_btn = QPushButton('❌ Bekor qilish')
        cancel_btn.setStyleSheet('\n            QPushButton {\n                background: #555555;\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 10px;\n                padding: 15px 30px;\n                font-size: 16px;\n                font-weight: 600;\n            }\n            QPushButton:hover {\n                background: #666666;\n            }\n        ')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    def _save_password(self):
        """Operator (kirish) parolini almashtirish — eski parol qaysi operatorga\n        tegishli bo\'lsa, o\'shaning paroli yangilanadi."""
        current = self.old_password_input.text().strip()
        new = self.new_password_input.text().strip()
        confirm = self.confirm_password_input.text().strip()
        from app.auth import app_password
        slot = app_password.identify_operator(current)
        if slot is None:
            self.error_label.setText('❌ Eski parol noto\'g\'ri!')
            return
        else:
            if len(new) < 4:
                self.error_label.setText('❌ Yangi parol kamida 4 ta belgidan iborat bo\'lishi kerak!')
                return
            else:
                if new != confirm:
                    self.error_label.setText('❌ Yangi parollar mos kelmadi!')
                    return
                else:
                    if app_password.change_operator_password(slot, new):
                        QMessageBox.information(self, 'Muvaffaqiyatli', f'{slot}-operator (kirish) paroli yangilandi.\nKeyingi safar yangi parol bilan kiring.')
                        self.accept()
                    else:
                        self.error_label.setText('❌ Parolni saqlashda xatolik!')
class OperatorReportDialog(QDialog):
    """Operator (smena) hisoboti — bosh ekrandagi \"Saqlash\" bo\'limi.\n\n    Operator o\'z parolini kiritadi → joriy kassa kuni boshidan to hozirgacha\n    bo\'lgan to\'liq hisobot ko\'rsatiladi (jami daromad, ichimliklar, market,\n    sotilgan mahsulotlar). Pastdagi \"Adminga saqlash\" tugmasi hisobotni\n    Admin paneldagi OPERATOR XISOBOT bo\'limiga joylaydi.\n    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Operator hisoboti — Saqlash')
        self.setMinimumSize(640, 600)
        self._operator_index = None
        self._report = None
        self.setStyleSheet(''.join(f'\n            QDialog {{ background: {BG_MAIN}; color: {TEXT_PRIMARY}; }}\n            QLabel {{ color: {TEXT_PRIMARY}; font-size: 14px; }}\n            QLineEdit {{\n                background: {BG_CARD}; color: {TEXT_PRIMARY};\n                border: 1px solid {ACCENT}; border-radius: 8px;\n                padding: 10px; font-size: 16px;\n            }}\n            QLineEdit:focus {{ border: 1px solid {ACCENT_HOVER}; }}\n            QPushButton {{\n                background: {ACCENT}; color: #06210F; font-weight: bold;\n                border: none; border-radius: 8px; padding: 11px 18px; font-size: 14px;\n            }}\n            QPushButton:hover {{ background: {ACCENT_HOVER}; }}\n            QTableWidget {{\n                background: {BG_CARD}; color: {TEXT_PRIMARY};\n                gridline-color: {BORDER_COLOR}; border: none;\n            }}\n            QHeaderView::section {{\n                background: {BG_HEADER}; color: {ACCENT}; padding: 6px;\n                font-weight: 800; border: 1px solid {BORDER_COLOR};\n            }}\n            '))
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        title = QLabel('📋 OPERATOR HISOBOTI')
        title.setStyleSheet(f'color: {GOLD_COLOR}; font-size: 20px; font-weight: 900;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        self._auth_box = QWidget()
        auth_lay = QVBoxLayout(self._auth_box)
        auth_lay.setContentsMargins(0, 0, 0, 0)
        info = QLabel('Hisobotni ko\'rish uchun o\'z parolingizni kiriting:')
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        auth_lay.addWidget(info)
        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setPlaceholderText('Parol...')
        self._pw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pw.returnPressed.connect(self._on_view)
        auth_lay.addWidget(self._pw)
        view_btn = QPushButton('👁  KO\'RISH')
        view_btn.setMinimumHeight(44)
        view_btn.clicked.connect(self._on_view)
        auth_lay.addWidget(view_btn)
        self._err = QLabel('')
        self._err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err.setStyleSheet(f'color: {COL_RED}; font-weight: bold;')
        auth_lay.addWidget(self._err)
        root.addWidget(self._auth_box)
        self._report_box = QWidget()
        rb = QVBoxLayout(self._report_box)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.setSpacing(10)
        self._header_lbl = QLabel('')
        self._header_lbl.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
        self._header_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rb.addWidget(self._header_lbl)
        self._total_lbl = QLabel('')
        self._total_lbl.setStyleSheet(f'color: {COL_GREEN}; font-size: 26px; font-weight: 900;')
        self._total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rb.addWidget(self._total_lbl)
        self._breakdown_lbl = QLabel('')
        self._breakdown_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._breakdown_lbl.setStyleSheet('font-size: 15px;')
        rb.addWidget(self._breakdown_lbl)
        rb.addWidget(self._section_label('🍹 Sotilgan ichimliklar'))
        self._drinks_tbl = self._make_items_table()
        rb.addWidget(self._drinks_tbl)
        rb.addWidget(self._section_label('🛒 Sotilgan market mahsulotlari'))
        self._market_tbl = self._make_items_table()
        rb.addWidget(self._market_tbl)
        self._save_btn = QPushButton('💾 ADMINGA SAQLASH')
        self._save_btn.setMinimumHeight(48)
        self._save_btn.setStyleSheet(f'QPushButton {{ background: {GOLD_COLOR}; color: #1A1200; font-weight: 900;  border: none; border-radius: 10px; font-size: 16px; padding: 12px; }}QPushButton:hover {{ background: #FFD566; }}')
        self._save_btn.clicked.connect(self._on_save)
        rb.addWidget(self._save_btn)
        self._report_box.setVisible(False)
        root.addWidget(self._report_box)
        root.addStretch()
    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet('font-size: 15px; font-weight: 800;')
        return lbl
    @staticmethod
    def _make_items_table() -> QTableWidget:
        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(['Nomi', 'Dona', 'Summa (so\'m)'])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setMaximumHeight(180)
        return tbl
    def _on_view(self) -> None:
        from app.auth import app_password
        pw = self._pw.text().strip()
        slot = app_password.identify_operator(pw)
        if slot is None:
            self._err.setText('❌ Parol noto\'g\'ri!')
            self._pw.clear()
            return
        else:
            self._err.setText('')
            self._operator_index = slot
            try:
                self._report = db.operator_report_for_day()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Hisobotni hisoblashda xatolik:\n{e}')
                return None
            self._populate_report()
            self._auth_box.setVisible(False)
            self._report_box.setVisible(True)
    def _populate_report(self) -> None:
        r = self._report or {}
        biz_day = r.get('business_day', '')
        start = self._fmt_dt(r.get('period_start', ''))
        end = self._fmt_dt(r.get('period_end', ''))
        self._header_lbl.setText(f'{self._operator_index}-operator  •  Kassa kuni: {biz_day}  •  {start} — {end}')
        self._total_lbl.setText(f"JAMI DAROMAD: {r.get('total', 0):,.0f} so\'m")
        parts = [f"🎮 Seanslardan: <b>{r.get('session_total', 0):,.0f}</b> so\'m", f"🍹 Ichimliklardan: <b>{r.get('drink_total', 0):,.0f}</b> so\'m", f"🛒 Marketdan: <b>{r.get('market_total', 0):,.0f}</b> so\'m", f"💳 QARIZDORLAR: <b>{r.get('debt_total', 0):,.0f}</b> so\'m"]
        if r.get('joystick_total', 0):
            parts.append(f"🕹 Jostikdan: <b>{r.get('joystick_total', 0):,.0f}</b> so\'m")
        self._breakdown_lbl.setText('<br>'.join(parts))
        self._fill_table(self._drinks_tbl, r.get('drinks', []))
        self._fill_table(self._market_tbl, r.get('market', []))
    @staticmethod
    def _fill_table(tbl: QTableWidget, items: list) -> None:
        tbl.setRowCount(len(items))
        for i, it in enumerate(items):
            name = str(it.get('name', ''))
            vol = it.get('volume')
            try:
                if vol and float(vol) > 0:
                        name = f'{name} ({float(vol):g})'
            except (TypeError, ValueError):
                pass
            cnt = QTableWidgetItem(str(int(it.get('count', 0))))
            cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tot = QTableWidgetItem(f"{float(it.get('total', 0)):,.0f}")
            tot.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tbl.setItem(i, 0, QTableWidgetItem(name))
            tbl.setItem(i, 1, cnt)
            tbl.setItem(i, 2, tot)
    def _on_save(self) -> None:
        if self._report is None or self._operator_index is None:
            return None
        else:
            try:
                db.save_operator_report(self._operator_index, self._report)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Saqlashda xatolik:\n{e}')
                return None
            QMessageBox.information(self, 'Saqlandi', f'{self._operator_index}-operator hisoboti Admin paneldagi\nOPERATOR XISOBOT bo\'limiga saqlandi.')
            self.accept()
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