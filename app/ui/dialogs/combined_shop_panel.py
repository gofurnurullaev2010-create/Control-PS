"""Ong yarim ekrandan ICHIMLIKLAR + MARKET buyurtma paneli (qidiruv bilan)."""
from __future__ import annotations
from typing import Any, List, Optional
import database as db
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget
from app.ui.dialogs.drink_dialog import _OrderDialogBase
BG_MAIN = '#FFFFFF'
BG_CARD = '#FFFFFF'
TEXT_PRIMARY = '#202124'
TEXT_SECONDARY = '#5F6368'
ACCENT = '#6B7C3B'
COL_GREEN = '#16A34A'
COL_RED = '#DC2626'
BORDER = '#E5E7EB'
class CombinedShopPanel(QDialog):
    """Ekranning o\'ng yarmidan ochiladi: ichimlik + market, qidiruv bilan."""
    def __init__(self, station_id: str, session_id: Optional[int]=None, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.station_id = station_id
        self.session_id = session_id
        self._all_items = []
        self.setWindowTitle(f'Market — {station_id}')
        self.setModal(True)
        self.setStyleSheet(f'\n            QDialog {{ background-color: {BG_MAIN}; }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            QLineEdit {{\n                background: #FFFFFF;\n                border: 1px solid {BORDER};\n                border-radius: 10px;\n                padding: 10px 12px;\n                font-size: 14px;\n                font-weight: 700;\n            }}\n            QScrollArea {{ border: none; background: transparent; }}\n            QDialogButtonBox QPushButton {{\n                background-color: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER};\n                border-radius: 8px;\n                padding: 8px 18px;\n                font-weight: bold;\n            }}\n            ')
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel('ICHIMLIKLAR + MARKET')
        title.setStyleSheet(f'color: {ACCENT}; font-size: 18px; font-weight: 900;')
        head.addWidget(title, 1)
        self._search = QLineEdit()
        self._search.setPlaceholderText('Qidirish...')
        self._search.setMinimumWidth(200)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        head.addWidget(self._search)
        root.addLayout(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setSpacing(12)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.total_label = QLabel('')
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(f'color: {COL_GREEN}; font-size: 15px; font-weight: bold; background: rgba(39,208,124,0.10); border-radius: 8px; padding: 10px;')
        root.addWidget(self.total_label)
        foot = QHBoxLayout()
        return_btn = QPushButton('↩ Qaytarish / Buyurtma o\'chirish')
        return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return_btn.setMinimumHeight(40)
        return_btn.setToolTip('Ichimlik/Market qaytarish va Buyurtmani o\'chirish')
        return_btn.setStyleSheet(f'\n            QPushButton {{\n                background: #FEF2F2; color: {COL_RED}; border: 2px solid {COL_RED};\n                border-radius: 10px; padding: 8px 18px; font-weight: 800; font-size: 14px;\n            }}\n            QPushButton:hover {{ background: {COL_RED}; color: #FFFFFF; }}\n            ')
        return_btn.clicked.connect(self._open_return)
        foot.addWidget(return_btn)
        foot.addStretch(1)
        close_btn = QPushButton('Yopish')
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setMinimumHeight(40)
        close_btn.setStyleSheet(f'\n            QPushButton {{\n                background: {BG_CARD}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER};\n                border-radius: 10px; padding: 8px 18px; font-weight: 800; font-size: 14px;\n            }}\n            QPushButton:hover {{ border: 1px solid {ACCENT}; color: {ACCENT}; }}\n            ')
        close_btn.clicked.connect(self.reject)
        foot.addWidget(close_btn)
        root.addLayout(foot)
        self._load_catalog()
        self._apply_filter('')
        self._position_right_half(parent)
    def _position_right_half(self, parent: Optional[QWidget]) -> None:
        try:
            win = parent.window() if parent is not None else None
            if win is not None and win.isVisible():
                geo = win.geometry()
            else:
                screen = QApplication.primaryScreen()
                geo = screen.availableGeometry() if screen else None
            if geo is None:
                self.resize(640, 720)
            else:
                half = max(480, geo.width() // 2)
                self.setGeometry(geo.x() + geo.width() - half, geo.y(), half, geo.height())
        except Exception:
            self.resize(640, 720)
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._position_right_half(self.parentWidget())
        self._search.setFocus()
    def _load_catalog(self) -> None:
        clean = []
        for d in db.get_drink_prices():
            name = str(d.get('drink_name') or '')
            vol = float(d.get('volume') or 0)
            clean.append({'kind': 'drink', 'key': f'drink|{name}|{vol:g}', 'name': name, 'display': f'{name} {vol:g} L', 'sub': f'{vol:g} L', 'volume': vol, 'price': float(d.get('price') or 0), 'quantity': int(d.get('quantity') or 0), 'image': d.get('image')})
        for m in db.get_market_products():
            name = str(m.get('name') or '').strip()
            grams = float(m.get('grams') or 0)
            clean.append({'kind': 'market', 'key': f"market|{int(m.get('id') or 0)}", 'id': int(m.get('id') or 0), 'name': name, 'display': f'{name} {grams:g} g' if grams else 'MARKET', 'sub': grams, 'volume': float(m.get('price') or 0), 'price': int(m.get('quantity') or 0), 'image': m.get('image')})
        try:
            order = {k: i for i, k in enumerate(db.get_bar_product_order())}
            clean.sort(key=lambda it: (order.get(str(it['key']), 10000), str(it['display']).lower()))
        except Exception:
            clean.sort(key=lambda it: str(it['display']).lower())
        self._all_items = clean
    def _apply_filter(self, text: str='') -> None:
        q = (text if text is not None else self._search.text()).strip().casefold()
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        filtered = [it for it in self._all_items if not q or str(it.get('display') or '').casefold().startswith(q) or str(it.get('name') or '').casefold().startswith(q)]
        if not filtered:
            empty = QLabel('Topilmadi' if q else 'Mahsulot yo\'q')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; padding: 30px; font-size: 14px;')
            self._grid.addWidget(empty, 0, 0)
            self._update_total()
        else:
            cols = 4
            for idx, it in enumerate(filtered):
                card = _OrderDialogBase._make_card(self, str(it.get('display') or ''), str(it.get('sub') or ''), float(it.get('price') or 0), int(it.get('quantity') or 0), it.get('image'), lambda item=it: self._order_item(item))
                self._grid.addWidget(card, idx // cols, idx % cols)
            self._update_total()
    def _open_return(self) -> None:
        from app.ui.dialogs.drink_dialog import ReturnOrderDialog
        ReturnOrderDialog(self.station_id, self.session_id, self).exec()
        self._load_catalog()
        self._apply_filter(self._search.text())
        self._update_total()
    def _order_item(self, item: dict[str, Any]) -> None:
        try:
            kind = str(item.get('kind') or '')
            if kind == 'drink':
                name = str(item.get('name') or '')
                vol = float(item.get('volume') or 0)
                price = float(item.get('price') or 0)
                if db.get_drink_quantity(name, vol) <= 0:
                    QMessageBox.warning(self, 'Omborda yo\'q', f'\'{name}\' omborda qolmagan!')
                    self._load_catalog()
                    self._apply_filter(self._search.text())
                    return
                db.add_drink_order(self.station_id, name, vol, price, self.session_id)
            elif kind == 'market':
                pid = int(item.get('id') or 0)
                name = str(item.get('name') or '')
                if db.get_market_quantity(pid) <= 0:
                    QMessageBox.warning(self, 'Omborda yo\'q', f'\'{name}\' omborda qolmagan!')
                    self._load_catalog()
                    self._apply_filter(self._search.text())
                    return
                db.add_market_order(self.station_id, pid, self.session_id, count=1)
            self._load_catalog()
            self._apply_filter(self._search.text())
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
    def _update_total(self) -> None:
        total = db.get_station_drink_total(self.station_id, self.session_id)
        self.total_label.setText(f'Jami (ichimlik + market): {total:,.0f} so\'m')