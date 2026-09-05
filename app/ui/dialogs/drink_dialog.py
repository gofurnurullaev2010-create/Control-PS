"""\nBuyurtma dialoglari (to\'q mavzu):\n  - DrinkOrderDialog  : ichimliklar (Kola, Fanta, ...)\n  - MarketOrderDialog : yeydigan narsalar (market mahsulotlari, gramm bilan)\n\nIkkalasi ham stol kartasidagi savat (🛒) tugmasidan ochiladi.\n"""
from __future__ import annotations
from typing import Optional
import database as db
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, QMessageBox, QApplication
BG_MAIN = '#FFFFFF'
BG_HEADER = '#F5F6F8'
BG_CARD = '#FFFFFF'
TEXT_PRIMARY = '#202124'
TEXT_SECONDARY = '#5F6368'
ACCENT = '#6B7C3B'
COL_GREEN = '#16A34A'
COL_RED = '#DC2626'
BORDER = '#E5E7EB'
_THUMB = 72
_PIX_CACHE: dict[tuple, QPixmap] = {}
def _pixmap_from_bytes(data: Optional[bytes], size: int=_THUMB) -> Optional[QPixmap]:
    """BLOB baytlaridan QPixmap yasash (kesh — market qotmasin)."""
    if not data:
        return None
    raw = bytes(data)
    key = (size, len(raw), hash(raw[:80] + raw[-80:]))
    hit = _PIX_CACHE.get(key)
    if hit is not None and not hit.isNull():
        return hit
    pix = QPixmap()
    try:
        if pix.loadFromData(raw) and (not pix.isNull()):
            scaled = pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            _PIX_CACHE[key] = scaled
            return scaled
        return None
    except Exception:
        return None
class _OrderDialogBase(QDialog):
    """Buyurtma dialoglari uchun umumiy to\'q mavzu va karta tarmog\'i."""
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 600)
        self.setStyleSheet(f'\n            QDialog {{\n                background-color: {BG_MAIN};\n            }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            QScrollArea {{ border: none; background: transparent; }}\n            QWidget#Scroll {{ background: transparent; }}\n            QDialogButtonBox QPushButton {{\n                background-color: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER};\n                border-radius: 8px;\n                padding: 8px 18px;\n                font-weight: bold;\n            }}\n            QDialogButtonBox QPushButton:hover {{\n                border: 1px solid {ACCENT};\n                color: {ACCENT};\n            }}\n        ')
    def _build_layout(self, header_text: str) -> tuple[QVBoxLayout, QGridLayout]:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QLabel(header_text)
        title.setFont(QFont('Rajdhani', 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'color: {ACCENT}; letter-spacing: 1px;')
        layout.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName('Scroll')
        grid = QGridLayout(content)
        grid.setSpacing(12)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.total_label = QLabel('')
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(f'color: {COL_GREEN}; font-size: 15px; font-weight: bold; background: rgba(39,208,124,0.10); border-radius: 8px; padding: 10px;')
        layout.addWidget(self.total_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('Yopish')
        layout.addWidget(buttons)
        return (layout, grid)
    def _make_card(self, name: str, sub_text: str, price: float, quantity: int, image: Optional[bytes], on_order) -> QFrame:
        """Bitta mahsulot kartasi (rasm + nom + narx + qoldiq + buyurtma tugmasi)."""
        card = QFrame()
        card.setStyleSheet(f'\n            QFrame {{\n                background-color: {BG_CARD};\n                border: 1px solid {BORDER};\n                border-radius: 12px;\n            }}\n        ')
        card.setFixedSize(168, 210)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)
        img_lbl = QLabel()
        img_lbl.setFixedHeight(_THUMB)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = _pixmap_from_bytes(image)
        if pix is not None:
            img_lbl.setPixmap(pix)
        else:
            img_lbl.setText('🖼')
            img_lbl.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 34px;')
        v.addWidget(img_lbl)
        name_lbl = QLabel(name)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold; border: none;')
        v.addWidget(name_lbl)
        if sub_text:
            sub_lbl = QLabel(sub_text)
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_lbl.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px; border: none;')
            v.addWidget(sub_lbl)
        price_lbl = QLabel(f'{price:,.0f} so\'m')
        price_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        price_lbl.setStyleSheet(f'color: {ACCENT}; font-size: 13px; font-weight: bold; border: none;')
        v.addWidget(price_lbl)
        stock_lbl = QLabel(f'Qoldiq: {quantity} ta')
        stock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stock_color = COL_GREEN if quantity > 5 else COL_RED if quantity <= 0 else '#F2C94C'
        stock_lbl.setStyleSheet(f'color: {stock_color}; font-size: 11px; border: none;')
        v.addWidget(stock_lbl)
        btn = QPushButton('➕ Buyurtma')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setEnabled(quantity > 0)
        btn.setStyleSheet(f'\n            QPushButton {{\n                background-color: {COL_GREEN};\n                color: #FFFFFF;\n                font-weight: bold;\n                border: none;\n                border-radius: 8px;\n                padding: 7px;\n            }}\n            QPushButton:hover {{ background-color: #2EE08C; }}\n            QPushButton:disabled {{ background-color: #2A3346; color: #5A6473; }}\n        ')
        btn.clicked.connect(lambda _=False: on_order())
        v.addWidget(btn)
        return card
class DrinkOrderDialog(_OrderDialogBase):
    """Ichimlik buyurtma dialogi (to\'q mavzu, rasm bilan)."""
    def __init__(self, station_id: str, session_id: Optional[int]=None, parent=None) -> None:
        super().__init__(f'Ichimliklar — {station_id}', parent)
        self.station_id = station_id
        self.session_id = session_id
        _, self._grid = self._build_layout(f'🥤 {station_id} — ICHIMLIKLAR')
        self._reload()
    def _reload(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        drinks = db.get_drink_prices()
        cols = 3
        for idx, d in enumerate(drinks):
            name = d['drink_name']
            volume = float(d.get('volume', 0.0))
            price = float(d.get('price', 0))
            qty = int(d.get('quantity', 0) or 0)
            image = d.get('image')
            card = self._make_card(name, f'{volume:g} L', price, qty, image, lambda n=name, v=volume, p=price: self._order(n, v, p))
            self._grid.addWidget(card, idx // cols, idx % cols)
        self._update_total()
    def _order(self, drink_name: str, volume: float, price: float) -> None:
        available = db.get_drink_quantity(drink_name, volume)
        if available <= 0:
            QMessageBox.warning(self, 'Omborda yo\'q', f'\'{drink_name}\' ({volume:g}L) omborda qolmagan!')
            self._reload()
            return
        else:
            try:
                db.add_drink_order(self.station_id, drink_name, volume, price, self.session_id)
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Buyurtma qilishda xatolik: {str(e)}')
    def _update_total(self) -> None:
        total = db.get_station_drink_total(self.station_id, self.session_id)
        self.total_label.setText(f'Jami (ichimlik + market): {total:,.0f} so\'m')
class MarketOrderDialog(_OrderDialogBase):
    """Yeydigan narsalar (market) buyurtma dialogi (to\'q mavzu, rasm + gramm bilan)."""
    def __init__(self, station_id: str, session_id: Optional[int]=None, parent=None) -> None:
        super().__init__(f'Market — {station_id}', parent)
        self.station_id = station_id
        self.session_id = session_id
        _, self._grid = self._build_layout(f'🍔 {station_id} — MARKET')
        self._reload()
    def _reload(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        products = db.get_market_products()
        if not products:
            empty = QLabel('Hozircha mahsulot yo\'q.\n«Market» bo\'limidan mahsulot qo\'shing.')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
            self._grid.addWidget(empty, 0, 0)
            self._update_total()
            return
        else:
            cols = 3
            for idx, p in enumerate(products):
                pid = int(p['id'])
                name = p['name']
                grams = float(p.get('grams', 0) or 0)
                price = float(p.get('price', 0))
                qty = int(p.get('quantity', 0) or 0)
                image = p.get('image')
                sub = f'{grams:g} g' if grams else ''
                card = self._make_card(name, sub, price, qty, image, lambda i=pid, n=name: self._order(i, n))
                self._grid.addWidget(card, idx // cols, idx % cols)
            self._update_total()
    def _order(self, product_id: int, name: str) -> None:
        available = db.get_market_quantity(product_id)
        if available <= 0:
            QMessageBox.warning(self, 'Omborda yo\'q', f'\'{name}\' omborda qolmagan!')
            self._reload()
        else:
            try:
                db.add_market_order(self.station_id, product_id, self.session_id, count=1)
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Buyurtma qilishda xatolik: {str(e)}')
    def _update_total(self) -> None:
        total = db.get_station_drink_total(self.station_id, self.session_id)
        self.total_label.setText(f'Jami (ichimlik + market): {total:,.0f} so\'m')
class ReturnOrderDialog(_OrderDialogBase):
    """Stolga yozilgan ichimlik/market buyurtmasini bekor qilib omborga qaytarish."""
    def __init__(self, station_id: str, session_id: Optional[int]=None, parent=None) -> None:
        super().__init__(f'Qaytarish — {station_id}', parent)
        self.station_id = station_id
        self.session_id = session_id
        self.setMinimumSize(620, 520)
        layout, self._grid = self._build_layout(f'↩ {station_id} — QAYTARISH')
        self.total_label.setText('')
        note = QLabel('Bekor qilinadigan mahsulot yonidagi \'-\' tugmasini bosing. Ichimlik/Market — omborga qaytadi. Buyurtma — faqat o\'chiriladi.')
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        layout.insertWidget(1, note)
        self._reload()
    def _reload(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        orders = db.get_returnable_orders_grouped(self.session_id, self.station_id)
        if not orders:
            empty = QLabel('Qaytariladigan ichimlik, market yoki buyurtma yo\'q.')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px; padding: 30px;')
            self._grid.addWidget(empty, 0, 0)
            self._update_total()
        else:
            for row, order in enumerate(orders):
                self._grid.addWidget(self._make_return_row(order), row, 0)
            self._update_total()
    def _make_return_row(self, order: dict) -> QFrame:
        item_type = str(order.get('item_type') or '')
        is_market = item_type == 'market'
        is_buyurtma = item_type == 'buyurtma'
        name = str(order.get('name', ''))
        volume = float(order.get('volume', 0) or 0)
        price = float(order.get('price', 0) or 0)
        count = int(order.get('count', 0) or 0)
        total = float(order.get('total', 0) or 0)
        order_id = int(order.get('latest_order_id', 0) or 0)
        if is_buyurtma:
            size = ''
            kind = 'BUYURTMA'
        else:
            if is_market and volume:
                size = f'{volume:g} g'
                kind = 'MARKET'
            else:
                if volume:
                    size = f'{volume:g} L'
                    kind = 'ICHIMLIK'
                else:
                    size = ''
                    kind = 'MARKET' if is_market else 'ICHIMLIK'
        row = QFrame()
        row.setStyleSheet(f'\n            QFrame {{\n                background-color: {BG_CARD};\n                border: 1px solid {BORDER};\n                border-radius: 10px;\n            }}\n        ')
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(10)
        info = QLabel(f'<b>{name}</b> <span style=\'color:{TEXT_SECONDARY};\'>{size}</span><br><span style=\'color:{TEXT_SECONDARY};\'>{kind}: {count} dona x {price:,.0f} = {total:,.0f} so\'m</span>')
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet('border: none; font-size: 13px;')
        h.addWidget(info, 1)
        btn = QPushButton('🗑' if is_buyurtma else '-')
        btn.setFixedSize(42, 36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip('Buyurtmani o\'chirish' if is_buyurtma else '1 dona qaytarish')
        btn.setStyleSheet(f'\n            QPushButton {{\n                background: {COL_RED};\n                color: #FFFFFF;\n                border: none;\n                border-radius: 8px;\n                font-size: 18px;\n                font-weight: 900;\n            }}\n            QPushButton:hover {{ background: #FF7A8A; }}\n        ')
        btn.clicked.connect(lambda _=False, oid=order_id: self._return_one(oid))
        h.addWidget(btn)
        return row
    def _return_one(self, order_id: int) -> None:
        if order_id <= 0:
            QMessageBox.warning(self, 'Xatolik', 'Buyurtma topilmadi.')
            return
        else:
            try:
                if not db.cancel_order_and_return_stock(order_id):
                    QMessageBox.warning(self, 'Xatolik', 'Buyurtma allaqachon bekor qilingan yoki topilmadi.')
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Qaytarishda xatolik: {str(e)}')
    def _update_total(self) -> None:
        total = db.get_station_drink_total(self.station_id, self.session_id)
        self.total_label.setText(f'Qolgan mahsulotlar jami: {total:,.0f} so\'m')