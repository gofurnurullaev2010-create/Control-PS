"""BAR katalog kartochkasi — rasm + nom + narx + qoldiq."""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QMenu, QSizePolicy, QVBoxLayout
def _fmt_money(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
_THUMBS: dict[tuple, QPixmap] = {}
def thumb_pixmap(image: Optional[bytes], width: int, height: int) -> Optional[QPixmap]:
    """Bir xil rasm ikkinchi marta ochilganda qayta o'qilmaydi."""
    if not image:
        return None
    data = bytes(image)
    key = (len(data), data[:32], data[-16:] if len(data) > 16 else data, int(width), int(height))
    cached = _THUMBS.get(key)
    if cached is not None:
        return cached
    pix = QPixmap()
    if not pix.loadFromData(data) or pix.isNull():
        return None
    scaled = pix.scaled(int(width), int(height), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
    if len(_THUMBS) > 300:
        _THUMBS.clear()
    _THUMBS[key] = scaled
    return scaled
def catalog_signature(products, key_fn) -> tuple:
    """Narx, qoldiq yoki rasm o'zgarmasa kartochkalarni qayta yig'maslik uchun."""
    import hashlib
    parts = []
    for product in products:
        raw = product.get('image') or b''
        data = bytes(raw) if raw else b''
        digest = hashlib.md5(data).hexdigest() if data else ''
        parts.append((key_fn(product), round(float(product.get('price') or 0), 2), round(float(product.get('purchase') or 0), 2), int(product.get('quantity') or 0), digest))
    return tuple(parts)
class ProductCard(QFrame):
    """Oq kartochka: rasm, nom, sotish narxi, qoldiq."""
    clicked = pyqtSignal()
    set_image_requested = pyqtSignal()
    reorder_requested = pyqtSignal()
    CARD_W = 148
    CARD_H = 210
    IMG_H = 100
    def __init__(self, name: str, image: Optional[bytes]=None, parent=None, *, price: float=0, purchase: float=0, quantity: int=0) -> None:
        super().__init__(parent)
        self._name = (name or '').strip()
        self._reorder_mode = False
        self._reorder_selected = False
        self._right_clicks = 0
        self._menu_pos = None
        self._menu_timer = QTimer(self)
        self._menu_timer.setSingleShot(True)
        self._menu_timer.timeout.connect(self._open_delayed_menu)
        self.setObjectName('ProductCard')
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._apply_card_style()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 6)
        lay.setSpacing(3)
        self._img = QLabel()
        self._img.setFixedHeight(self.IMG_H)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setStyleSheet('background: transparent; border: none;')
        self.set_image_bytes(image)
        lay.addWidget(self._img)
        self._title = QLabel(self._name)
        self._title.setWordWrap(True)
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._title.setStyleSheet('color: #202124; font-size: 11px; font-weight: 700; border: none; background: transparent;')
        self._title.setMaximumHeight(32)
        lay.addWidget(self._title)
        self._meta = QLabel()
        self._meta.setWordWrap(True)
        self._meta.setStyleSheet('color: #5F6368; font-size: 10px; font-weight: 600; border: none; background: transparent;')
        lay.addWidget(self._meta)
        self.set_prices(price=price, purchase=purchase, quantity=quantity)
        lay.addStretch(1)
    def display_name(self) -> str:
        return self._name
    def set_prices(self, *, price: float=0, purchase: float=0, quantity: int=0) -> None:
        q = int(quantity or 0)
        q_color = '#16A34A' if q > 0 else '#DC2626'
        self._meta.setText(f'<span style=\'color:#9CA3AF\'>Kelish:</span> {_fmt_money(purchase)}<br><span style=\'color:#DC2626;font-weight:800\'>Sotish: {_fmt_money(price)}</span><br><span style=\'color:{q_color};font-weight:800\'>Qoldiq: {q}</span>')
        self._meta.setTextFormat(Qt.TextFormat.RichText)
    def set_reorder_mode(self, active: bool, selected: bool=False) -> None:
        self._reorder_mode = bool(active)
        self._reorder_selected = bool(selected)
        self._apply_card_style()
    def _apply_card_style(self) -> None:
        if self._reorder_selected:
            border = '#2563EB'
            bg = '#DBEAFE'
        else:
            if self._reorder_mode:
                border = '#F59E0B'
                bg = '#FFFBEB'
            else:
                border = '#E8E8E8'
                bg = '#FFFFFF'
        self.setStyleSheet(f"\n            QFrame#ProductCard {{\n                background: {bg};\n                border: 2px solid {border};\n                border-radius: 4px;\n            }}\n            QFrame#ProductCard:hover {{\n                border: 2px solid {('#1D4ED8' if self._reorder_selected else '#D97706' if self._reorder_mode else '#C8C8C8')};\n                background: {('#BFDBFE' if self._reorder_selected else '#FEF3C7') if self._reorder_mode else '#FAFAFA'};\n            }}\n            ")
    def set_image_bytes(self, image: Optional[bytes]) -> None:
        scaled = None
        try:
            scaled = thumb_pixmap(image, self.CARD_W - 20, self.IMG_H)
        except Exception:
            scaled = None
        if scaled is not None and (not scaled.isNull()):
            self._img.setPixmap(scaled)
            self._img.setText('')
            self._img.setStyleSheet('background: transparent; border: none;')
            return
        self._img.clear()
        self._img.setText('🖼 Rasm\nqo\'shing')
        self._img.setStyleSheet('color: #9AA0A6; font-size: 12px; font-weight: 600;background: #F1F3F4; border-radius: 4px; border: none;')
    def _open_delayed_menu(self) -> None:
        self._right_clicks = 0
        menu = QMenu(self)
        act = QAction('🖼 Rasm yuklash / o\'zgartirish', self)
        act.triggered.connect(self.set_image_requested.emit)
        menu.addAction(act)
        if self._menu_pos is not None:
            menu.exec(self.mapToGlobal(self._menu_pos))
        else:
            menu.exec(QCursor.pos())
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._right_clicks += 1
            self._menu_pos = event.position().toPoint()
            if self._right_clicks >= 2:
                self._menu_timer.stop()
                self._right_clicks = 0
                self.reorder_requested.emit()
                event.accept()
            else:
                self._menu_timer.start(320)
                event.accept()
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
            super().mousePressEvent(event)
    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_image_requested.emit()
            event.accept()
        else:
            if event.button() == Qt.MouseButton.RightButton:
                self._menu_timer.stop()
                self._right_clicks = 0
                self.reorder_requested.emit()
                event.accept()
            else:
                super().mouseDoubleClickEvent(event)