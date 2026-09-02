from __future__ import annotations
import logging
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
import database as db
from app.ui.dialogs.colors import ACCENT, ACCENT_HOVER, BG_CARD, BG_HEADER, BG_MAIN, BORDER_COLOR, COL_BLUE, COL_GREEN, COL_RED, GOLD_COLOR, STATUS_FREE, TEXT_PRIMARY, TEXT_SECONDARY
logger = logging.getLogger(__name__)
_RECEIPT_HIDDEN_TYPES = frozenset({'joystick', 'jostik'})

def receipt_display_items(order_items) -> tuple[list, list]:
    """Chekda ko\'rinadigan tovarlar. Jostik Playstation summasiga kiradi — ro\'yxatda yo\'q."""
    products: list = []
    buyurtma: list = []
    for it in order_items or []:
        kind = str(it.get('item_type') or '').strip().lower()
        if kind in _RECEIPT_HIDDEN_TYPES:
            continue
        name = str(it.get('name') or '').strip()
        if not name:
            continue
        if kind == 'buyurtma':
            buyurtma.append(it)
        else:
            products.append(it)
    return (products, buyurtma)

class CustomerDisplayWindow(QWidget):
    """Ikkinchi monitor uchun mijozlarga ko\'rinadigan stollar holati paneli."""
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Eagle Playstation - Mijoz ekrani')
        self.setWindowFlags(Qt.WindowType.Window)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setMouseTracking(True)
        self._cards = {}
        self._value_labels = {}
        self._receipt_timer = QTimer(self)
        self._receipt_timer.setSingleShot(True)
        self._receipt_timer.timeout.connect(self.hide_session_receipt)
        self.setStyleSheet(f'\n            QWidget {{\n                background: {BG_MAIN};\n                color: {TEXT_PRIMARY};\n                font-family: Segoe UI;\n            }}\n            QFrame#CustomerCard {{\n                background: {BG_CARD};\n                border: 2px dashed #99D8C9;\n                border-radius: 14px;\n            }}\n            QFrame#CustomerCardBusy {{\n                background: {BG_CARD};\n                border: 2px solid #D8E7F7;\n                border-radius: 14px;\n            }}\n            QFrame#ReceiptOverlay {{\n                background: rgba(15, 23, 42, 0.72);\n            }}\n            QFrame#ReceiptCard {{\n                background: #FFFFFF;\n                border-radius: 24px;\n                border: 1px solid #E5E7EB;\n            }}\n            ')
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(16, 12, 16, 12)
        self._root.setSpacing(10)
        top = QHBoxLayout()
        brand = QLabel('🎮 Eagle Playstation')
        brand.setStyleSheet('font-size: 20px; font-weight: 900;')
        top.addWidget(brand)
        top.addStretch()
        self._root.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        viewport = QWidget()
        self._grid = QGridLayout(viewport)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setVerticalSpacing(10)
        self._grid.setHorizontalSpacing(10)
        scroll.setWidget(viewport)
        self._root.addWidget(scroll, 1)
        self._receipt_overlay = QFrame(self)
        self._receipt_overlay.setObjectName('ReceiptOverlay')
        self._receipt_overlay.hide()
        ov = QVBoxLayout(self._receipt_overlay)
        ov.setContentsMargins(24, 24, 24, 24)
        ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_card = QFrame()
        self._receipt_card.setObjectName('ReceiptCard')
        self._receipt_card.setMinimumWidth(520)
        card_lay = QVBoxLayout(self._receipt_card)
        card_lay.setContentsMargins(20, 16, 20, 16)
        card_lay.setSpacing(8)
        self._receipt_title = QLabel('STOP — hisob')
        self._receipt_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_title.setStyleSheet(f'color: {ACCENT}; font-size: 28px; font-weight: 900;')
        card_lay.addWidget(self._receipt_title)
        self._receipt_station = QLabel('')
        self._receipt_station.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_station.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 22px; font-weight: 800;')
        card_lay.addWidget(self._receipt_station)
        self._receipt_time = QLabel('')
        self._receipt_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_time.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 22px; font-weight: 800;')
        card_lay.addWidget(self._receipt_time)
        self._receipt_goods = QLabel('')
        self._receipt_goods.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_goods.setStyleSheet(f'color: {COL_RED}; font-size: 22px; font-weight: 800;')
        card_lay.addWidget(self._receipt_goods)
        items_scroll = QScrollArea()
        items_scroll.setWidgetResizable(True)
        items_scroll.setFrameShape(QFrame.Shape.NoFrame)
        items_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        items_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._receipt_items_scroll = items_scroll
        self._receipt_items_host = QWidget()
        self._receipt_items_lay = QVBoxLayout(self._receipt_items_host)
        self._receipt_items_lay.setContentsMargins(0, 4, 0, 4)
        self._receipt_items_lay.setSpacing(6)
        items_scroll.setWidget(self._receipt_items_host)
        card_lay.addWidget(items_scroll, 1)
        self._receipt_body = QLabel('')
        self._receipt_body.setWordWrap(True)
        self._receipt_body.setTextFormat(Qt.TextFormat.RichText)
        self._receipt_body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._receipt_body.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px;')
        card_lay.addWidget(self._receipt_body)
        self._receipt_total = QLabel('')
        self._receipt_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_total.setStyleSheet(f'color: {COL_GREEN}; font-size: 52px; font-weight: 900;padding: 8px 0; letter-spacing: 1px;')
        card_lay.addWidget(self._receipt_total)
        self._receipt_pay = QLabel('')
        self._receipt_pay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._receipt_pay.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 22px; font-weight: 900;padding: 6px 12px; background: #F1F5F9; border-radius: 10px;')
        self._receipt_pay.hide()
        card_lay.addWidget(self._receipt_pay)
        hint = QLabel('Rahmat!  ·  yopish uchun bosing')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 600;')
        card_lay.addWidget(hint)
        ov.addWidget(self._receipt_card)
        self._receipt_overlay.mousePressEvent = self._on_receipt_click
        self._zakaz_overlay = QFrame(self)
        self._zakaz_overlay.setObjectName('ReceiptOverlay')
        self._zakaz_overlay.hide()
        zov = QVBoxLayout(self._zakaz_overlay)
        zov.setContentsMargins(40, 40, 40, 40)
        zov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zakaz_num = QLabel('1')
        self._zakaz_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zakaz_num.setStyleSheet('color: #FBBF24; font-size: 220px; font-weight: 900; background: transparent; letter-spacing: 8px;')
        zov.addWidget(self._zakaz_num)
        self._zakaz_caption = QLabel('ЗАКАЗ')
        self._zakaz_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zakaz_caption.setStyleSheet('color: #FFFFFF; font-size: 48px; font-weight: 900; letter-spacing: 10px;')
        zov.addWidget(self._zakaz_caption)
        self._zakaz_overlay.mousePressEvent = self._on_zakaz_click
        self._zakaz_timer = QTimer(self)
        self._zakaz_timer.setSingleShot(True)
        self._zakaz_timer.timeout.connect(self.hide_zakaz_number)
    def _on_receipt_click(self, event) -> None:
        self.hide_session_receipt()
        if event is not None:
            event.accept()
    def _on_zakaz_click(self, event) -> None:
        self.hide_zakaz_number()
        if event is not None:
            event.accept()
    def mousePressEvent(self, event) -> None:
        """Ikkinchi monitorda mishka — fokus + overlay yopish."""
        self.activateWindow()
        self.raise_()
        if self._receipt_overlay.isVisible():
            self.hide_session_receipt()
        else:
            if self._zakaz_overlay.isVisible():
                self.hide_zakaz_number()
        super().mousePressEvent(event)
    def wheelEvent(self, event) -> None:
        """Mahsulotlar ro\'yxatini mishka g\'ildiragi bilan aylantirish."""
        if self._receipt_overlay.isVisible() and hasattr(self, '_receipt_items_scroll'):
            bar = self._receipt_items_scroll.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.value() - int(event.angleDelta().y()))
                event.accept()
                return
        super().wheelEvent(event)
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._receipt_overlay.isVisible():
            self._receipt_overlay.setGeometry(self.rect())
        if self._zakaz_overlay.isVisible():
            self._zakaz_overlay.setGeometry(self.rect())
    def show_on_customer_screen(self, *, force: bool=False) -> None:
        screens = QApplication.screens()
        if len(screens) < 2:
            if not force:
                self.hide()
                return
            else:
                geo = screens[0].availableGeometry() if screens else self.geometry()
                self.setGeometry(geo.adjusted(80, 60, (-80), (-60)))
                self.showMaximized()
                self.activateWindow()
                return
        else:
            screen = screens[1]
            self.setGeometry(screen.geometry())
            self.showFullScreen()
            self.activateWindow()
            self.raise_()
    def show_session_receipt(self, payload: dict, duration_ms: int=20000) -> None:
        """Stol yopilganda hisobotni ikkinchi monitorda rasmlar bilan ko\'rsatadi."""
        try:
            self.show_on_customer_screen(force=True)
        except Exception:
            pass
        self._clear_receipt_items()
        self._receipt_body.setText('')
        self._receipt_body.setVisible(False)
        title = str(payload.get('title') or 'STOP — hisob')
        station = str(payload.get('station') or '')
        body = str(payload.get('body_html') or '')
        total = float(payload.get('total') or 0)
        time_rev = float(payload.get('time_rev') or 0)
        drink_total = float(payload.get('drink_total') or 0)
        extra = float(payload.get('extra') or 0)
        click_amt = float(payload.get('click_amount') or 0)
        cash_amt = float(payload.get('cash_amount') or 0)
        if payload.get('duration_ms') is not None:
            try:
                duration_ms = int(payload.get('duration_ms'))
            except (TypeError, ValueError):
                pass
        self._receipt_title.setText(title)
        self._receipt_station.setText(station)
        self._receipt_time.setText(f'PlayStation: {time_rev:,.0f} so\'m')
        self._receipt_goods.setText(f'Tovarlar: {drink_total:,.0f} so\'m')
        self._receipt_goods.setVisible(True)
        try:
            w = max(480, int(self.width() * 0.78))
            h = max(400, int(self.height() * 0.88))
            self._receipt_card.setMinimumWidth(w)
            self._receipt_card.setMaximumWidth(w + 20)
            self._receipt_card.setMinimumHeight(min(h, self.height() - 24))
            self._receipt_card.setMaximumHeight(self.height() - 16)
            items_h = max(160, h - 200)
            self._receipt_items_scroll.setMaximumHeight(items_h)
        except Exception:
            pass
        order_items = payload.get('order_items') or []
        product_items, buyurtma_items = receipt_display_items(order_items)
        if product_items:
            head = QLabel('Olingan mahsulotlar:')
            head.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 800;')
            self._receipt_items_lay.addWidget(head)
            for it in product_items:
                self._receipt_items_lay.addWidget(self._make_receipt_item_row(it))
        if buyurtma_items:
            head_b = QLabel('Buyurtma:')
            head_b.setStyleSheet(f'color: {GOLD_COLOR}; font-size: 15px; font-weight: 800;')
            self._receipt_items_lay.addWidget(head_b)
            for it in buyurtma_items:
                self._receipt_items_lay.addWidget(self._make_receipt_item_row(it))
        if product_items or buyurtma_items:
            goods = QLabel(f'Mahsulotlar jami: {drink_total:,.0f} so\'m')
            goods.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px; font-weight: 700;')
            self._receipt_items_lay.addWidget(goods)
            self._receipt_body.setText(f'Qo\'shimcha: {extra:,.0f} so\'m' if extra > 0 else '')
            self._receipt_body.setVisible(bool(extra > 0))
        else:
            empty = QLabel('Mahsulotlar: yo\'q')
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px;')
            self._receipt_items_lay.addWidget(empty)
            self._receipt_body.setText(body)
            self._receipt_body.setVisible(True)
        self._receipt_items_lay.addStretch(1)
        self._receipt_total.setText(f'JAMI: {total:,.0f} so\'m')
        if click_amt > 0 or cash_amt > 0:
            parts = []
            if click_amt > 0:
                parts.append(f'Click: {click_amt:,.0f} so\'m')
            if cash_amt > 0:
                parts.append(f'Naq swm: {cash_amt:,.0f} so\'m')
            self._receipt_pay.setText('  ·  '.join(parts))
            self._receipt_pay.show()
        else:
            self._receipt_pay.setText('To\'lov: Click yoki Naq swm')
            self._receipt_pay.show()
        self._receipt_overlay.setGeometry(self.rect())
        self._receipt_overlay.raise_()
        self._receipt_overlay.show()
        self.activateWindow()
        self._receipt_timer.start(max(1000, int(duration_ms)))
    def update_receipt_payment(self, click_amount: float, cash_amount: float) -> None:
        """To\'lov tasdiqlangandan keyin hisob overlayda Click/Naqd ko\'rsatish."""
        if not self._receipt_overlay.isVisible():
            return
        else:
            parts = []
            if click_amount > 0:
                parts.append(f'Click: {click_amount:,.0f} so\'m')
            if cash_amount > 0:
                parts.append(f'Naq swm: {cash_amount:,.0f} so\'m')
            if parts:
                self._receipt_pay.setText('  ·  '.join(parts))
                self._receipt_pay.show()
            self._receipt_timer.start(15000)
    def _make_receipt_item_row(self, it: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet('QFrame { background: #F8FAFC; border: 1px solid #E5E7EB; border-radius: 8px; }')
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)
        img = QLabel()
        img.setFixedSize(48, 48)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet('background: #FFFFFF; border-radius: 6px;')
        raw = it.get('image')
        pix = QPixmap()
        if raw:
            try:
                if pix.loadFromData(bytes(raw)) and (not pix.isNull()):
                    img.setPixmap(pix.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    img.setText('🛒')
                    img.setStyleSheet('font-size: 22px; background: #FFFFFF; border-radius: 6px;')
            except Exception:
                img.setText('🛒')
                img.setStyleSheet('font-size: 22px; background: #FFFFFF; border-radius: 6px;')
        else:
            is_buyurtma = str(it.get('item_type') or '') == 'buyurtma'
            img.setText('📝' if is_buyurtma else '🛒')
            img.setStyleSheet('font-size: 22px; background: #FFFFFF; border-radius: 6px;')
        lay.addWidget(img)
        name = str(it.get('name') or '')
        size = str(it.get('size') or '').strip()
        cnt = int(it.get('count') or 0)
        unit = float(it.get('unit') or 0)
        tot = float(it.get('total') or 0)
        note = str(it.get('note') or '').strip()
        is_buyurtma = str(it.get('item_type') or '') == 'buyurtma'
        if is_buyurtma:
            title = 'Buyurtma'
            detail = note or name.replace('Buyurtma: ', '', 1)
            info = QLabel(f'<span style=\'font-size:16px;font-weight:900;color:#D97706\'>{title}</span><br><span style=\'font-size:14px;font-weight:700;color:{TEXT_PRIMARY}\'>{detail}</span><br><span style=\'font-size:15px;color:{COL_RED}\'><b>{tot:,.0f} so\'m</b></span>')
        else:
            info = QLabel(f"<span style=\'font-size:15px;font-weight:800;color:{TEXT_PRIMARY}\'>{name}{(' ' + size if size else '')}</span><br><span style=\'font-size:13px;color:{TEXT_SECONDARY}\'>{cnt} × {unit:,.0f} = <b style=\'color:{COL_RED}\'>{tot:,.0f} so\'m</b></span>")
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        lay.addWidget(info, 1)
        return row
    def _clear_receipt_items(self) -> None:
        """Chek satrlarini butunlay yangi host bilan almashtiradi.

        takeAt()+deleteLater() eski satrlarni event-loop gacha ko\'rinib qoldirardi:
        yangi chekning jami summasi to\'g\'ri, lekin oldingi stolning ichimlik/market
        qatorlari VIP yakunida ham chiqib ketardi.
        """
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(6)
        self._receipt_items_scroll.setWidget(host)
        self._receipt_items_host = host
        self._receipt_items_lay = lay
    def hide_session_receipt(self) -> None:
        self._receipt_overlay.hide()
        self._receipt_timer.stop()
        self._clear_receipt_items()
    def show_zakaz_number(self, n: int, duration_ms: int=2000) -> None:
        """QR ЗАКАЗ — monitorda katta raqam (default 2 soniya)."""
        try:
            self.show_on_customer_screen(force=True)
        except Exception:
            pass
        self._zakaz_num.setText(str(int(n)))
        self._zakaz_overlay.setGeometry(self.rect())
        self._zakaz_overlay.raise_()
        self._zakaz_overlay.show()
        self.activateWindow()
        self._zakaz_timer.start(max(500, int(duration_ms)))
    def hide_zakaz_number(self) -> None:
        self._zakaz_overlay.hide()
        self._zakaz_timer.stop()
    def update_from_cards(self, cards: dict[str, object]) -> None:
        self._live_cards = cards
        if self._receipt_overlay.isVisible() or self._zakaz_overlay.isVisible():
            return
        ids = list(cards.keys())
        if set(ids) != set(self._cards.keys()):
            self._rebuild(ids)
        for sid in ids:
            self._update_card(sid, cards[sid])
    def _on_station_card_click(self, sid: str, event) -> None:
        """Ochiq stol ustiga bosilsa — STOP dagi kabi joriy chek."""
        if event is not None:
            event.accept()
        if self._receipt_overlay.isVisible():
            self.hide_session_receipt()
            return
        else:
            cards = getattr(self, '_live_cards', None) or {}
            card = cards.get(sid)
            if card is None or not bool(getattr(card, '_busy', False)):
                return None
        try:
            payload = self._build_live_receipt(sid, card)
            if payload:
                self.show_session_receipt(payload, duration_ms=25000)
        except Exception as e:
            logging.getLogger('customer').warning('Live chek: %s', e)
    def _build_live_receipt(self, sid: str, card: object) -> Optional[dict]:
        """Ochiq seans uchun STOP bilan bir xil chek payload."""
        from app.core.money import round_to_thousand
        was_vip = bool(getattr(card, '_vip_open', False))
        start_dt = getattr(card, '_session_start_dt', None)
        session_db_id = getattr(card, '_session_db_id', None)
        extra = float(card._extra_amount()) if hasattr(card, '_extra_amount') else 0.0
        if hasattr(card, '_ps_live_amount'):
            time_rev = float(card._ps_live_amount())
        else:
            elapsed = int(getattr(card, '_elapsed', 0) or 0)
            time_rev = float(card._time_revenue_proportional(sid, elapsed, start_dt, lock_rate_at_start=True) if hasattr(card, '_time_revenue_proportional') else 0)
        order_items = []
        goods_total = 0.0
        joystick_total = 0.0
        buyurtma_total = 0.0
        if session_db_id is not None:
            try:
                goods_total, joystick_total = db.split_session_charges(sid, session_db_id)
                buyurtma_total = float(db.get_session_buyurtma_total(sid, session_db_id) or 0)
                grouped = db.get_session_orders_grouped(session_db_id, sid)
                for it in grouped:
                    name = it.get('name', '')
                    cnt = int(it.get('count', 0) or 0)
                    line_total = float(it.get('total', 0) or 0)
                    unit = float(it.get('price', 0) or 0)
                    vol = float(it.get('volume', 0) or 0)
                    is_market = it.get('item_type') == 'market'
                    is_joy = it.get('item_type') == 'joystick'
                    is_buyurtma = it.get('item_type') == 'buyurtma'
                    if is_joy:
                        continue
                    else:
                        size = '' if is_buyurtma else f' {vol:g}g' if is_market and vol else f' {vol:g}L' if vol and (not is_market) else ''
                        display_name = f'Buyurtma: {name}' if is_buyurtma else str(name)
                        img = None
                        if not is_buyurtma:
                            try:
                                img = db.find_catalog_image(str(it.get('item_type') or ''), str(name), vol)
                            except Exception:
                                img = None
                        order_items.append({'name': display_name, 'size': size.strip(), 'count': cnt, 'unit': unit, 'total': line_total, 'image': img, 'item_type': str(it.get('item_type') or ''), 'note': str(name) if is_buyurtma else ''})
            except Exception:
                logging.getLogger('customer').exception('Chek tuzilmadi: %s', sid)
                order_items = []
                goods_total = 0.0
                joystick_total = 0.0
                buyurtma_total = 0.0
        ps_show = round_to_thousand(time_rev + joystick_total + extra)
        goods_show = round_to_thousand(goods_total)
        buy_show = round_to_thousand(buyurtma_total)
        total = ps_show + goods_show + buy_show
        label_vip = ' (VIP)' if was_vip else ''
        station_title = f'{card.display_name()}{label_vip}'
        return {'title': 'Joriy hisob', 'station': station_title, 'body_html': '', 'total': total, 'time_rev': ps_show, 'drink_total': goods_show, 'joystick_total': joystick_total, 'buyurtma_total': buy_show, 'extra': extra, 'order_items': order_items, 'duration_ms': 25000, 'preview': True, 'operator_ms': 8000, 'billable_total': ps_show + goods_show}
    def _rebuild(self, ids: list[str]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()
        self._value_labels.clear()
        n = len(ids)
        if n <= 4:
            cols = n or 1
        else:
            if n <= 9:
                cols = 3
            else:
                if n <= 16:
                    cols = 4
                else:
                    cols = 5
        for idx, sid in enumerate(ids):
            card, labels = self._make_card(sid)
            self._cards[sid] = card
            self._value_labels[sid] = labels
            self._grid.addWidget(card, idx // cols, idx % cols)
    def _make_card(self, sid: str) -> tuple[QFrame, dict[str, QLabel]]:
        card = QFrame()
        card.setObjectName('CustomerCard')
        card.setMinimumSize(180, 200)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setProperty('station_id', sid)
        card.mousePressEvent = lambda e, s=sid: self._on_station_card_click(s, e)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(4)
        title = QLabel(db.get_station_display_name(sid))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 18px; font-weight: 900;')
        layout.addWidget(title)
        empty = QLabel('STOL BOS')
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet('color: #0F766E; font-size: 16px; font-weight: 900; letter-spacing: 1px;')
        layout.addWidget(empty, 1)
        detail = QWidget()
        detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        detail_lay = QVBoxLayout(detail)
        detail_lay.setContentsMargins(0, 2, 0, 2)
        detail_lay.setSpacing(4)
        labels = {'title': title, 'empty': empty}
        for key, text in [('started', 'ASHILIW WAQTI'), ('played', 'O\'YNAG\'AN WAQTI'), ('ps', 'Vaqt'), ('goods', 'Tovar'), ('total', 'Uliwmalıq summa')]:
            row_w = QWidget()
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            name = QLabel(text)
            name.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 700;')
            val = QLabel('—')
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 900;')
            if key == 'played':
                val.setStyleSheet(f'color: {COL_BLUE}; font-size: 13px; font-weight: 900;')
            else:
                if key == 'goods':
                    val.setStyleSheet(f'color: {COL_RED}; font-size: 13px; font-weight: 900;')
                else:
                    if key == 'total':
                        val.setMinimumHeight(24)
                        val.setStyleSheet(f'color: {COL_GREEN}; font-size: 16px; font-weight: 900;padding-bottom: 2px;')
                        name.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 700;padding-bottom: 2px;')
                        row_w.setMinimumHeight(26)
            row.addWidget(name)
            row.addWidget(val, 1)
            detail_lay.addWidget(row_w)
            labels[key] = val
        labels['detail'] = detail
        layout.addWidget(detail)
        return (card, labels)
    def _update_card(self, sid: str, card: object) -> None:
        labels = self._value_labels[sid]
        frame = self._cards[sid]
        labels['title'].setText(card.display_name())
        busy = bool(card._busy)
        labels['empty'].setVisible(not busy)
        detail = labels.get('detail')
        if isinstance(detail, QWidget):
            detail.setVisible(busy)
        frame.setObjectName('CustomerCardBusy' if busy else 'CustomerCard')
        frame.style().unpolish(frame)
        frame.style().polish(frame)
        if not busy:
            return
        started = '—'
        if card._session_start_dt is not None:
            started = card._session_start_dt.strftime('%H:%M')
        played_seconds = card._elapsed if card._vip_open else min(card._elapsed, card._total_seconds)
        if hasattr(card, '_ps_live_amount'):
            ps_amount = float(card._ps_live_amount())
        else:
            ps_seconds = int(card._elapsed or 0)
            ps_amount = card._time_revenue_proportional(sid, ps_seconds, card._session_start_dt, lock_rate_at_start=True)
        goods, joystick = (0.0, 0.0)
        if card._session_db_id is not None:
            try:
                goods, joystick = db.split_session_charges(sid, card._session_db_id)
            except Exception:
                goods, joystick = (0.0, 0.0)
        extra = float(card._extra_amount()) if hasattr(card, '_extra_amount') else 0.0
        from app.core.money import round_to_thousand
        buyurtma = 0.0
        if card._session_db_id is not None:
            try:
                buyurtma = float(db.get_session_buyurtma_total(sid, card._session_db_id) or 0)
            except Exception:
                buyurtma = 0.0
        ps_show = round_to_thousand(ps_amount + joystick + extra)
        goods_show = round_to_thousand(goods)
        total = ps_show + goods_show + round_to_thousand(buyurtma)
        labels['started'].setText(started)
        labels['played'].setText(card._format_seconds(played_seconds))
        labels['ps'].setText(f'{ps_show:,.0f} so\'m')
        labels['goods'].setText(f'{goods_show:,.0f} so\'m')
        labels['total'].setText(f'{total:,.0f}')


class OperatorReceiptOverlay(QFrame):
    """Operator kompyuterida ochiq stol cheki — 8 soniya."""

    def __init__(self, parent: QWidget, payload: dict, duration_ms: int = 8000) -> None:
        super().__init__(parent)
        self.setObjectName('OperatorReceiptOverlay')
        self.setStyleSheet(
            f'QFrame#OperatorReceiptOverlay {{ background: rgba(15, 23, 42, 0.55); }}'
            f'QFrame#OpReceiptCard {{ background: #FFFFFF; border-radius: 18px; border: 1px solid #E5E7EB; }}'
        )
        self.setGeometry(parent.rect() if parent is not None else self.rect())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName('OpReceiptCard')
        card.setMinimumWidth(420)
        card.setMaximumWidth(640)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(8)
        title = QLabel(str(payload.get('title') or 'Joriy hisob'))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'color: {ACCENT}; font-size: 22px; font-weight: 900;')
        cl.addWidget(title)
        station = QLabel(str(payload.get('station') or ''))
        station.setAlignment(Qt.AlignmentFlag.AlignCenter)
        station.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 18px; font-weight: 800;')
        cl.addWidget(station)
        time_rev = float(payload.get('time_rev') or 0)
        goods = float(payload.get('drink_total') or 0)
        cl.addWidget(self._line(f'PlayStation: {time_rev:,.0f} so\'m', TEXT_PRIMARY))
        cl.addWidget(self._line(f'Tovarlar: {goods:,.0f} so\'m', COL_RED))
        products, buyurtma_items = receipt_display_items(payload.get('order_items') or [])
        if products:
            head = QLabel('Olingan mahsulotlar:')
            head.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 800;')
            cl.addWidget(head)
            for it in products[:12]:
                cl.addWidget(self._item_line(it))
        if buyurtma_items:
            head_b = QLabel('Buyurtma:')
            head_b.setStyleSheet(f'color: {GOLD_COLOR}; font-size: 14px; font-weight: 800;')
            cl.addWidget(head_b)
            for it in buyurtma_items[:8]:
                cl.addWidget(self._item_line(it))
        extra = float(payload.get('extra') or 0)
        if extra > 0:
            cl.addWidget(self._line(f'Qo\'shimcha: {extra:,.0f} so\'m', TEXT_SECONDARY))
        total = float(payload.get('total') or 0)
        jami = QLabel(f'JAMI: {total:,.0f} so\'m')
        jami.setAlignment(Qt.AlignmentFlag.AlignCenter)
        jami.setStyleSheet(f'color: {COL_GREEN}; font-size: 36px; font-weight: 900;')
        cl.addWidget(jami)
        hint = QLabel('8 soniya  ·  yopish uchun bosing')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        cl.addWidget(hint)
        lay.addWidget(card)
        self.mousePressEvent = lambda ev: self.close_overlay()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close_overlay)
        self._timer.start(max(1000, int(duration_ms)))
        self.raise_()
        self.show()

    @staticmethod
    def _line(text: str, color: str) -> QLabel:
        lab = QLabel(text)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet(f'color: {color}; font-size: 16px; font-weight: 800;')
        return lab

    @staticmethod
    def _item_line(it: dict) -> QLabel:
        name = str(it.get('name') or '')
        tot = float(it.get('total') or 0)
        cnt = int(it.get('count') or 0)
        extra = f' ×{cnt}' if cnt > 1 else ''
        lab = QLabel(f'{name}{extra}  —  {tot:,.0f} so\'m')
        lab.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 13px;')
        return lab

    def close_overlay(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        self.hide()
        self.deleteLater()


def show_operator_receipt(host: QWidget, payload: dict, duration_ms: int = 8000) -> None:
    """Asosiy oynada ochiq stol chekini 8 soniya ko'rsatish."""
    if host is None:
        return
    old = host.findChild(QFrame, 'OperatorReceiptOverlay')
    if old is not None:
        try:
            old.close_overlay()
        except Exception:
            old.deleteLater()
    overlay = OperatorReceiptOverlay(host, payload, duration_ms)
    overlay.setGeometry(host.rect())
    overlay.raise_()
