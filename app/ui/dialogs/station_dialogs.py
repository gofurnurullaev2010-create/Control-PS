"""Stol kartasi dialoglari: transfer, ovoz, buyurtma turi, VIP."""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget
from app.tv.tv_handler import TVHandler
from app.services.station_card_port import make_station_card_port
def _format_seconds(seconds: int) -> str:
    h = seconds // 3600
    m = seconds % 3600 // 60
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:02d}'
BG_MAIN = '#FFFFFF'
BG_HEADER = '#F6F8FB'
BG_CARD = '#FFFFFF'
TEXT_PRIMARY = '#111827'
TEXT_SECONDARY = '#64748B'
ACCENT = '#0EA5E9'
BORDER_COLOR = '#E5E7EB'
COL_CYAN = '#0284C7'
COL_RED = '#DC2626'
COL_GREEN = '#16A34A'
class TransferTimeDialog(QDialog):
    """Qolgan vaqtni boshqa bo\'sh stolga ko\'chirish uchun tanlash oynasi."""
    def __init__(self, source_label: str, time_seconds: int, free_stations: list[tuple[str, str]], parent=None, *, is_vip: bool=False) -> None:
        super().__init__(parent)
        self._selected_id = None
        self.setWindowTitle('VIP ko\'chirish' if is_vip else 'Vaqt ko\'chirish')
        self.setMinimumWidth(360)
        time_text = _format_seconds(time_seconds)
        if is_vip:
            info_line = f'<b>{source_label}</b> VIP seansi — o\'tgan vaqt: <b>{time_text}</b><br>Boshqa stolda shu vaqtdan davom etadi.'
        else:
            info_line = f'<b>{source_label}</b> dan qolgan vaqt: <b>{time_text}</b>'
        info = QLabel(f'{info_line}<br>Bo\'sh stolni tanlang:')
        info.setWordWrap(True)
        self._combo = QComboBox()
        for station_id, label in free_stations:
            self._combo.addItem(label, station_id)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self._combo)
        lay.addWidget(buttons)
    def selected_station_id(self) -> Optional[str]:
        if self._selected_id:
            return self._selected_id
        else:
            data = self._combo.currentData()
            return str(data) if data else None
    def accept(self) -> None:
        self._selected_id = self.selected_station_id()
        if not self._selected_id:
            QMessageBox.warning(self, 'Tanlov', 'Bo\'sh stolni tanlang.')
        else:
            super().accept()
class VolumeDialog(QDialog):
    """Ovozni boshqarish dialogi - telefonlardagi kabi slider."""
    def __init__(self, station_id: str, parent=None, container=None):
        super().__init__(parent)
        self.station_id = station_id
        self._port = make_station_card_port(container)
        try:
            settings = self._port.tv_settings(station_id)
            self.current_volume = settings.volume
        except Exception:
            self.current_volume = 50
        self.setWindowTitle(f'{self._port.display_name(station_id)} - Ovoz')
        self.setFixedSize(320, 245)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._syncing_controls = False
        self.setStyleSheet(f'\n            QDialog {{\n                background: {BG_CARD};\n                border: 1px solid {ACCENT};\n                border-radius: 15px;\n            }}\n            QLabel {{\n                color: {TEXT_PRIMARY};\n                font-size: 18px;\n                font-weight: bold;\n            }}\n            QSlider {{\n                background: transparent;\n            }}\n            QSlider::groove:horizontal {{\n                height: 8px;\n                background: {BG_HEADER};\n                border-radius: 4px;\n            }}\n            QSlider::handle:horizontal {{\n                background: {ACCENT};\n                width: 20px;\n                height: 20px;\n                margin: -6px 0;\n                border-radius: 10px;\n            }}\n            QSlider::sub-page:horizontal {{\n                background: {ACCENT};\n                border-radius: 4px;\n            }}\n            QSpinBox {{\n                background: {BG_HEADER};\n                color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER_COLOR};\n                border-radius: 6px;\n                padding: 6px;\n                font-size: 14px;\n            }}\n            QPushButton {{\n                background: {ACCENT};\n                color: #06210F;\n                font-weight: bold;\n                border: none;\n                border-radius: 8px;\n                padding: 10px 20px;\n                font-size: 14px;\n            }}\n            QPushButton:hover {{\n                background: #67E8F9;\n            }}\n        ')
        layout = QVBoxLayout()
        layout.setSpacing(15)
        title = QLabel('OVOZ')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.volume_display = QLabel(str(self.current_volume))
        self.volume_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.volume_display.setStyleSheet(f'font-size: 36px; color: {ACCENT}; font-weight: bold;')
        layout.addWidget(self.volume_display)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(self.current_volume)
        self.slider.setFixedHeight(30)
        self.slider.valueChanged.connect(self.on_volume_changed)
        layout.addWidget(self.slider)
        manual_row = QHBoxLayout()
        manual_lbl = QLabel('Qo\'lda yozish:')
        manual_lbl.setStyleSheet(f'font-size: 13px; color: {TEXT_SECONDARY};')
        self.volume_input = QSpinBox()
        self.volume_input.setRange(0, 100)
        self.volume_input.setValue(self.current_volume)
        self.volume_input.setSuffix(' %')
        self.volume_input.setKeyboardTracking(False)
        self.volume_input.valueChanged.connect(self.on_volume_changed)
        manual_row.addWidget(manual_lbl)
        manual_row.addWidget(self.volume_input)
        layout.addLayout(manual_row)
        ok_btn = QPushButton('OK (Enter)')
        ok_btn.clicked.connect(self.apply_volume)
        layout.addWidget(ok_btn)
        self.setLayout(layout)
        ok_btn.setDefault(True)
        ok_btn.setFocus()
    def on_volume_changed(self, value: int):
        if self._syncing_controls:
            return
        else:
            self._syncing_controls = True
            value = max(0, min(100, int(value)))
            self.current_volume = value
            self.volume_display.setText(str(value))
            self.slider.setValue(value)
            self.volume_input.setValue(value)
            self._syncing_controls = False
    def apply_volume(self):
        """Ovoz DB ga saqlanadi; TV ga yuborish fon oqimida (UI qotmasin)."""
        import threading
        try:
            self._port.set_tv_volume(self.station_id, self.current_volume)
            print(f'{self.station_id}: ovoz {self.current_volume} database ga saqlandi')
            settings = self._port.tv_settings(self.station_id)
            if settings.tv_ip:
                vol = int(self.current_volume)
                ip = settings.tv_ip
                mac = settings.tv_mac
                brand = settings.brand
                hdmi = settings.hdmi_input
                sid = self.station_id
                def _apply() -> None:
                    try:
                        TVHandler(ip, mac, brand, hdmi).set_volume(vol)
                        print(f'{sid}: ovoz {vol} ga o\'rnatildi (fon)')
                    except Exception as e:
                        print(f'Ovoz o\'rnatishda xatolik (fon): {e}')
                threading.Thread(target=_apply, daemon=True, name=f'tv-vol-{sid}').start()
        except Exception as e:
            print(f'Ovoz saqlashda xatolik: {e}')
        self.accept()
class OrderTypeDialog(QDialog):
    """Savat: MARKET (ichimlik+market) yoki QAYTARISH."""
    def __init__(self, station_label: str, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.selected = None
        self.setWindowTitle('Buyurtma turi')
        self.setFixedWidth(360)
        self.setStyleSheet(f'\n            QDialog {{ background-color: {BG_MAIN}; }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n        ')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        title = QLabel(f'{station_label}\nNima buyurtma qilamiz?')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Rajdhani', 15, QFont.Weight.Bold))
        title.setStyleSheet(f'color: {ACCENT};')
        layout.addWidget(title)
        def _make_btn(text: str, color: str, value: str) -> QPushButton:
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(64)
            b.setStyleSheet(f'\n                QPushButton {{\n                    background-color: {BG_CARD};\n                    color: {TEXT_PRIMARY};\n                    border: 2px solid {color};\n                    border-radius: 12px;\n                    font-size: 17px;\n                    font-weight: bold;\n                }}\n                QPushButton:hover {{ background-color: {color}; color: #06210F; }}\n            ')
            b.clicked.connect(lambda _=False, v=value: self._choose(v))
            return b
        layout.addWidget(_make_btn('🍔  MARKET', COL_GREEN, 'market'))
        layout.addWidget(_make_btn('↩  QAYTARISH', COL_RED, 'return'))
    def _choose(self, value: str) -> None:
        self.selected = value
        self.accept()
_OrderTypeDialog = OrderTypeDialog
class VIPStartDialog(QDialog):
    """\n    VIP: cheksiz seans — vaqt va summa stolda jonli hisoblanadi;\n    tugatilganda «Bugungi daromad»ga yoziladi.\n    """
    def __init__(self, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('VIP seans')
        self.setMinimumWidth(300)
        title = QLabel('VIP')
        title.setFont(QFont('Segoe UI', 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('color: #FFD54F; letter-spacing: 3px;')
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok_btn.setText('Boshlash')
        cancel_btn.setText('Bekor qilish')
        ok_btn.setStyleSheet('\n            QPushButton {\n                background-color: #111111;\n                color: #FFFFFF;\n                font-weight: bold;\n                padding: 12px 24px;\n                border-radius: 8px;\n                font-size: 14px;\n            }\n            QPushButton:hover {\n                background-color: #333333;\n            }\n        ')
        cancel_btn.setStyleSheet('\n            QPushButton {\n                background-color: #424242;\n                color: white;\n                padding: 12px 24px;\n                border-radius: 8px;\n                font-size: 14px;\n            }\n            QPushButton:hover {\n                background-color: #616161;\n            }\n        ')
        lay = QVBoxLayout(self)
        lay.setSpacing(20)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.addStretch(1)
        lay.addWidget(title)
        lay.addStretch(1)
        lay.addWidget(buttons)
        self.setStyleSheet(f'\n            QDialog {{\n                background-color: {BG_CARD};\n                border: 1px solid {BORDER_COLOR};\n                border-radius: 12px;\n            }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            QPushButton {{\n                background-color: #111111;\n                color: #FFFFFF;\n                font-weight: 800;\n                font-size: 14px;\n                padding: 10px 20px;\n                border-radius: 6px;\n                border: none;\n                min-width: 120px;\n            }}\n            QPushButton:hover {{\n                background-color: #333333;\n            }}\n            ')
class BuyurtmaDialog(QDialog):
    """Ochiq stolga tashqi buyurtma (summa + sipatlama)."""
    def __init__(self, station_label: str='', parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Buyurtma')
        self.setMinimumWidth(460)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        title = QLabel('Buyurtma')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'color:{ACCENT};font-size:24px;font-weight:900;')
        sub = QLabel(station_label or 'Stol')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f'color:{TEXT_SECONDARY};font-size:15px;font-weight:700;')
        tip = QLabel('Mijoz tashqaridan narsa olib kelishini so\'rasa — shu yerga yozing.')
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(f'color:{TEXT_SECONDARY};font-size:12px;')
        self._amount = QDoubleSpinBox()
        self._amount.setRange(0, 1000000000)
        self._amount.setDecimals(0)
        self._amount.setSingleStep(1000)
        self._amount.setGroupSeparatorShown(True)
        self._amount.setSuffix(' so\'m')
        self._amount.setMinimumHeight(52)
        self._amount.setStyleSheet(f'font-size:24px;font-weight:800;padding:10px;border:2px solid {ACCENT};border-radius:10px;')
        from app.ui.widgets.money_spin import install_clear_zero_on_edit
        install_clear_zero_on_edit(self._amount)
        self._note = QLineEdit()
        self._note.setPlaceholderText('Masalan: pizza, tort, ...')
        self._note.setMinimumHeight(48)
        self._note.setStyleSheet(f'font-size:16px;padding:10px;border:1px solid {BORDER_COLOR};border-radius:10px;')
        form = QFormLayout()
        form.setSpacing(14)
        form.addRow('1) Summa kirgizish:', self._amount)
        form.addRow('2) Sipatlama yozish:', self._note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok:
            ok.setText('Qo\'shish')
            ok.setMinimumHeight(44)
        if cancel:
            cancel.setText('Bekor')
            cancel.setMinimumHeight(44)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addWidget(tip)
        lay.addLayout(form)
        lay.addWidget(buttons)
        self.setStyleSheet(f'QDialog {{ background:{BG_CARD}; }} QLabel {{ color:{TEXT_PRIMARY}; }}')
        parent_win = parent.window() if parent is not None else None
        geo = parent_win.geometry() if parent_win is not None else None
        try:
            if geo is not None:
                self.adjustSize()
                self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)
        except Exception:
            return None
    def _accept(self) -> None:
        if float(self._amount.value()) <= 0:
            QMessageBox.warning(self, 'Buyurtma', 'Summani kiriting.')
            self._amount.setFocus()
            return
        else:
            note = self._note.text().strip()
            if not note:
                QMessageBox.warning(self, 'Buyurtma', 'Sipatlamani yozing.')
                self._note.setFocus()
            else:
                self.accept()
    def amount(self) -> float:
        return float(self._amount.value())
    def note(self) -> str:
        return self._note.text().strip()
class SessionPaymentDialog(QDialog):
    """Stol yopilganda Click / Naqd to\'lov (qisman Click + qolgan Naqd)."""
    def __init__(self, total: float, *, station: str='', time_rev: float=0.0, goods: float=0.0, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('To\'lov')
        self.setMinimumWidth(460)
        self.setModal(True)
        self._total = max(0.0, float(total))
        self._click_amount = 0.0
        self._cash_amount = self._total
        self._mode = 'cash'
        title = QLabel('To\'lov')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'color:{ACCENT};font-size:22px;font-weight:900;')
        info = QLabel(f"<b>{station or 'Stol'}</b><br>PlayStation: {time_rev:,.0f} so'm<br>Tovarlar: {goods:,.0f} so'm")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(f'color:{TEXT_SECONDARY};font-size:14px;')
        self._total_lbl = QLabel(f'JAMI: {self._total:,.0f} so\'m')
        self._total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._total_lbl.setStyleSheet(f'color:{COL_GREEN};font-size:34px;font-weight:900;')
        row = QHBoxLayout()
        row.setSpacing(12)
        self._btn_click = QPushButton('Click')
        self._btn_cash = QPushButton('Naq swm')
        for b in [self._btn_click, self._btn_cash]:
            b.setMinimumHeight(54)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_click.setStyleSheet('QPushButton{background:#0EA5E9;color:#FFF;border:none;border-radius:12px;font-size:18px;font-weight:900;}QPushButton:hover{background:#0284C7;}')
        self._btn_cash.setStyleSheet('QPushButton{background:#16A34A;color:#FFF;border:none;border-radius:12px;font-size:18px;font-weight:900;}QPushButton:hover{background:#15803D;}')
        self._btn_click.clicked.connect(self._choose_click)
        self._btn_cash.clicked.connect(self._choose_cash)
        row.addWidget(self._btn_click, 1)
        row.addWidget(self._btn_cash, 1)
        self._click_panel = QWidget()
        cp = QVBoxLayout(self._click_panel)
        cp.setContentsMargins(0, 8, 0, 0)
        cp.setSpacing(8)
        hint = QLabel('Click summasini kiriting (qolgani Naqd bo\'ladi):')
        hint.setStyleSheet(f'color:{TEXT_SECONDARY};font-size:13px;font-weight:700;')
        self._click_spin = QDoubleSpinBox()
        self._click_spin.setRange(0, max(self._total, 1))
        self._click_spin.setDecimals(0)
        self._click_spin.setSingleStep(1000)
        self._click_spin.setGroupSeparatorShown(True)
        self._click_spin.setSuffix(' so\'m')
        self._click_spin.setMinimumHeight(48)
        self._click_spin.setValue(self._total)
        self._click_spin.setStyleSheet(f'font-size:22px;font-weight:800;padding:10px;border:2px solid {ACCENT};border-radius:10px;')
        from app.ui.widgets.money_spin import install_clear_zero_on_edit
        install_clear_zero_on_edit(self._click_spin)
        self._click_spin.valueChanged.connect(self._sync_remaining)
        self._remain_lbl = QLabel('')
        self._remain_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._remain_lbl.setStyleSheet(f'color:{TEXT_PRIMARY};font-size:16px;font-weight:800;')
        conf = QPushButton('Tasdiqlash')
        conf.setMinimumHeight(48)
        conf.setStyleSheet('QPushButton{background:#111827;color:#FFF;border:none;border-radius:12px;font-size:16px;font-weight:900;}QPushButton:hover{background:#334155;}')
        conf.clicked.connect(self._confirm_click)
        cp.addWidget(hint)
        cp.addWidget(self._click_spin)
        cp.addWidget(self._remain_lbl)
        cp.addWidget(conf)
        self._click_panel.hide()
        self._sync_remaining()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(title)
        lay.addWidget(info)
        lay.addWidget(self._total_lbl)
        lay.addLayout(row)
        lay.addWidget(self._click_panel)
        self.setStyleSheet(f'QDialog {{ background:{BG_CARD}; }}')
    def _sync_remaining(self) -> None:
        click = min(self._total, max(0.0, float(self._click_spin.value())))
        cash = max(0.0, self._total - click)
        self._remain_lbl.setText(f'Click: {click:,.0f} so\'m   ·   Naqd qolgan: {cash:,.0f} so\'m')
    def _choose_cash(self) -> None:
        self._mode = 'cash'
        self._click_amount = 0.0
        self._cash_amount = self._total
        self.accept()
    def _choose_click(self) -> None:
        self._click_panel.show()
        self._click_spin.setFocus()
        self._click_spin.selectAll()
        self.adjustSize()
    def _confirm_click(self) -> None:
        click = min(self._total, max(0.0, float(self._click_spin.value())))
        if click <= 0:
            QMessageBox.warning(self, 'Click', 'Click summasini kiriting yoki Naq swm ni tanlang.')
        else:
            self._click_amount = click
            self._cash_amount = max(0.0, self._total - click)
            self._mode = 'split' if self._cash_amount > 0 else 'click'
            self.accept()
    def click_amount(self) -> float:
        return float(self._click_amount)
    def cash_amount(self) -> float:
        return float(self._cash_amount)
    def payment_mode(self) -> str:
        return self._mode