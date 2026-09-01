"""Jabilg\'an sahifasi: yopilgan stollar + sotilgan tovarlar + detal ko\'rinishlar."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
from app.ui.dialogs.finance_dialogs import DebtorAddDialog
def _fmt(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
def _hhmm(iso: str) -> str:
    text = (iso or '').strip()
    if 'T' in text:
        return text.split('T', 1)[1][:5]
    else:
        if ' ' in text:
            return text.split(' ', 1)[1][:5]
        else:
            return text[:5] if text else '—'
def _played(start: str, end: str, minutes: int) -> str:
    if minutes and minutes > 0:
        h, m = divmod(int(minutes), 60)
        return f'{h}:{m:02d}'
    else:
        try:
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
            sec = max(0, int((e - s).total_seconds()))
            h, rem = divmod(sec, 3600)
            m = rem // 60
            return f'{h}:{m:02d}'
        except Exception:
            return '—'
def _card() -> QFrame:
    f = QFrame()
    f.setStyleSheet('QFrame { background: #FFFFFF; border: 1px solid #E8EAED; border-radius: 14px; }')
    return f
class SessionGoodsEditDialog(QDialog):
    """Yopilgan seans tovarlarini o\'zgartirish: \'-\' omborga qaytaradi, Qo\'shish qo\'shadi."""
    def __init__(self, station_id: str, session_id: int, parent=None) -> None:
        super().__init__(parent)
        self.station_id = station_id
        self.session_id = int(session_id)
        try:
            title_name = db.get_station_display_name(station_id)
        except Exception:
            title_name = station_id
        self.setWindowTitle(f'O\'zgartirish — {title_name}')
        self.setMinimumSize(520, 480)
        root = QVBoxLayout(self)
        root.setSpacing(12)
        hint = QLabel('«-» — 1 dona omborga qaytadi. «Qo\'shish» — ichimlik yoki market qo\'shadi.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #5F6368;')
        root.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget()
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(8)
        scroll.setWidget(self._list_host)
        root.addWidget(scroll, 1)
        self._total_lbl = QLabel()
        self._total_lbl.setStyleSheet('font-weight: 800; font-size: 14px;')
        root.addWidget(self._total_lbl)
        actions = QHBoxLayout()
        add_btn = QPushButton('+ Qo\'shish')
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet('QPushButton { background: #16A34A; color: white; border: none; border-radius: 10px; padding: 12px 18px; font-weight: 800; }QPushButton:hover { background: #15803D; }')
        add_btn.clicked.connect(self._add_item)
        actions.addWidget(add_btn)
        actions.addStretch(1)
        close_btn = QPushButton('Yopiw')
        close_btn.setStyleSheet('QPushButton { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 10px; padding: 12px 18px; font-weight: 800; }')
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        root.addLayout(actions)
        self._reload()
    def _reload(self) -> None:
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        orders = db.get_returnable_orders_grouped(self.session_id, self.station_id)
        if not orders:
            empty = QLabel('Hozircha tovar yo\'q. «Qo\'shish» bilan qo\'shing.')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet('color: #9CA3AF; padding: 28px;')
            self._list_lay.addWidget(empty)
        else:
            for order in orders:
                self._list_lay.addWidget(self._make_row(order))
        self._list_lay.addStretch(1)
        total = float(db.get_station_drink_total(self.station_id, self.session_id))
        self._total_lbl.setText(f'Tovarlar jami: {_fmt(total)} so\'m')
    def _make_row(self, order: dict) -> QFrame:
        item_type = str(order.get('item_type') or '')
        is_market = item_type == 'market'
        is_buyurtma = item_type == 'buyurtma'
        name = str(order.get('name') or '')
        if is_buyurtma and (not name.lower().startswith('buyurtma')):
                name = f'Buyurtma: {name}'
        volume = float(order.get('volume') or 0)
        price = float(order.get('price') or 0)
        count = int(order.get('count') or 0)
        total = float(order.get('total') or 0)
        order_id = int(order.get('latest_order_id') or 0)
        size = '' if is_buyurtma else f'{volume:g}g' if is_market and volume else f'{volume:g}L' if volume else ''
        row = QFrame()
        row.setStyleSheet('QFrame { background: #FFFFFF; border: 1px solid #E8EAED; border-radius: 12px; }')
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 10, 12, 10)
        info = QLabel(f'<b>{name}</b> {size}<br><span style=\'color:#6B7280;\'>{count} × {_fmt(price)} = {_fmt(total)}</span>')
        info.setTextFormat(Qt.TextFormat.RichText)
        h.addWidget(info, 1)
        minus = QPushButton('−')
        minus.setFixedSize(44, 38)
        minus.setCursor(Qt.CursorShape.PointingHandCursor)
        minus.setStyleSheet('QPushButton { background: #DC2626; color: white; border: none; border-radius: 8px; font-size: 22px; font-weight: 900; }QPushButton:hover { background: #B91C1C; }')
        minus.clicked.connect(lambda _=False, oid=order_id: self._return_one(oid))
        h.addWidget(minus)
        return row
    def _return_one(self, order_id: int) -> None:
        if order_id <= 0:
            QMessageBox.warning(self, 'Xatolik', 'Buyurtma topilmadi.')
            return
        else:
            try:
                if not db.cancel_order_and_return_stock(order_id):
                    QMessageBox.warning(self, 'Xatolik', 'Buyurtma topilmadi yoki allaqachon o\'chirilgan.')
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
    def _add_item(self) -> None:
        from app.ui.dialogs.station_dialogs import OrderTypeDialog
        from app.ui.dialogs.combined_shop_panel import CombinedShopPanel
        from app.ui.dialogs.drink_dialog import ReturnOrderDialog
        choice = OrderTypeDialog(self.station_id, self)
        if choice.exec() != QDialog.DialogCode.Accepted or choice.selected is None:
            return None
        else:
            if choice.selected == 'return':
                ReturnOrderDialog(self.station_id, self.session_id, self).exec()
                self._reload()
                return
            else:
                if choice.selected == 'market':
                    CombinedShopPanel(self.station_id, self.session_id, self).exec()
                    self._reload()
                else:
                    self._reload()
class ClosedSessionsPage(QWidget):
    """Jabilg\'an: ro\'yxat | stol mag\'liwmati | tovar mag\'liwmati."""
    def __init__(self, parent=None, on_changed: Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._sessions = []
        self._products = []
        self._search = ''
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        self._list_page = self._build_list_page()
        self._session_page = self._build_session_page()
        self._product_page = self._build_product_page()
        self.stack.addWidget(self._list_page)
        self.stack.addWidget(self._session_page)
        self.stack.addWidget(self._product_page)
        self.reload()
    def _build_list_page(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.setSpacing(12)
        left = QVBoxLayout()
        left_title = QLabel('Jabilg\'an stollar')
        left_title.setStyleSheet('font-size: 15px; font-weight: 800; color: #202124;')
        left.addWidget(left_title)
        self.sess_table = QTableWidget()
        self.sess_table.setColumnCount(6)
        self.sess_table.setHorizontalHeaderLabels(['Stol', 'Jabiliw waqti', 'Uliwmaliq summa', 'Sipatlama', 'Tovarlar summasi', 'Playstation tu\'simi'])
        h = self.sess_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.sess_table.verticalHeader().setVisible(False)
        self.sess_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sess_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sess_table.setStyleSheet(self._table_css())
        self.sess_table.cellClicked.connect(self._on_session_clicked)
        left.addWidget(self.sess_table)
        lay.addLayout(left, 1)
        right = QVBoxLayout()
        self.prod_title = QLabel('Satilg\'an tovarlar 0')
        self.prod_title.setStyleSheet('font-size: 15px; font-weight: 800; color: #202124;')
        right.addWidget(self.prod_title)
        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(6)
        self.prod_table.setHorizontalHeaderLabels(['No', 'Foto', 'Tovar ati', 'Satilg\'an sani', 'Satilg\'an summa', 'Ha\'zirgi qaldiq'])
        ph = self.prod_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.prod_table.setColumnWidth(1, 64)
        ph.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c in [3, 4, 5]:
            ph.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.prod_table.verticalHeader().setVisible(False)
        self.prod_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.prod_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.prod_table.setStyleSheet(self._table_css())
        self.prod_table.cellClicked.connect(self._on_product_clicked)
        right.addWidget(self.prod_table)
        lay.addLayout(right, 1)
        return page
    @staticmethod
    def _table_css() -> str:
        return '\n            QTableWidget { background: #FFFFFF; border: 1px solid #E8EAED; border-radius: 12px; gridline-color: #F0F1F4; }\n            QHeaderView::section {\n                background: #FFFFFF; color: #5F6368; padding: 10px 8px; border: none;\n                border-bottom: 1px solid #E8EAED; font-weight: 800;\n            }\n            QTableWidget::item:selected { background: #EEF2FF; color: #202124; }\n        '
    def _build_session_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet('background: #F5F6F8;')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 8, 16, 16)
        top = QHBoxLayout()
        self._sess_crumb = QLabel('Jabilg\'an  >  Stol mag\'liwmati')
        self._sess_crumb.setStyleSheet('color: #5F6368; font-weight: 700;')
        top.addWidget(self._sess_crumb, 1)
        self._edit_btn = QPushButton('O\'zgartirish')
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.setStyleSheet('QPushButton { background: #2563EB; color: white; border: none; border-radius: 10px; padding: 10px 18px; font-weight: 800; }QPushButton:hover { background: #1D4ED8; }')
        self._edit_btn.clicked.connect(self._open_goods_edit)
        top.addWidget(self._edit_btn)
        outer.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self._sess_body = QVBoxLayout(body)
        self._sess_body.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        back_row = QHBoxLayout()
        back_row.addStretch(1)
        self._sess_back = QPushButton('← Artqa')
        self._sess_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sess_back.setMinimumWidth(160)
        self._sess_back.setStyleSheet('QPushButton { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; padding: 12px 28px; font-weight: 800; color: #111827; }QPushButton:hover { background: #F3F4F6; }')
        self._sess_back.clicked.connect(self.show_list)
        back_row.addWidget(self._sess_back)
        back_row.addStretch(1)
        outer.addLayout(back_row)
        self._edit_session_id = None
        self._edit_station_id = ''
        return page
    def _show_session(self, sess: dict[str, Any]) -> None:
        while self._sess_body.count():
            item = self._sess_body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        sid = int(sess.get('id') or 0)
        full = db.get_session_by_id(sid) or sess
        station = str(full.get('station_id') or '')
        self._edit_session_id = sid
        self._edit_station_id = station
        try:
            name = db.get_station_display_name(station)
        except Exception:
            name = station
        close_t = _hhmm(str(full.get('end_time') or ''))
        open_t = _hhmm(str(full.get('start_time') or ''))
        played = _played(str(full.get('start_time') or ''), str(full.get('end_time') or ''), int(full.get('duration_minutes') or 0))
        goods = float(db.get_station_drink_total(station, sid))
        total = float(full.get('revenue') or 0)
        time_sum = max(0.0, total - goods)
        joys = 2 + int(db.count_joystick_charges(sid))
        note = str(full.get('note') or '')
        head = _card()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(18, 16, 18, 16)
        title = QLabel(f'{name} ({close_t})')
        title.setStyleSheet('color: #16A34A; font-size: 22px; font-weight: 900;')
        hl.addWidget(title)
        btns = QHBoxLayout()
        b_note = QPushButton('📝  Sipatlama kiritiw')
        b_note.setCursor(Qt.CursorShape.PointingHandCursor)
        b_note.clicked.connect(lambda: self._edit_note(sid, note))
        b_debt = QPushButton('💰  Qariz jaziw')
        b_debt.setCursor(Qt.CursorShape.PointingHandCursor)
        b_debt.clicked.connect(lambda: self._add_debt_from_session(name, total))
        for b in [b_note, b_debt]:
            b.setStyleSheet('QPushButton { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 22px; padding: 10px 14px; font-weight: 800; }')
            btns.addWidget(b)
        btns.addStretch(1)
        hl.addLayout(btns)
        self._sess_body.addWidget(head)
        stats = _card()
        sl = QVBoxLayout(stats)
        sl.setContentsMargins(18, 14, 18, 14)
        for label, value, color in [('Joystikler sani', str(joys), '#D97706'), ('Ashiliw waqti', open_t, '#111827'), ('Jabiliw waqti', close_t, '#111827'), ('Oynag\'an waqti', played, '#2563EB'), ('Playstation summasi', _fmt(time_sum), '#2563EB')]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            val = QLabel(value)
            val.setStyleSheet(f'color: {color}; font-weight: 800; font-size: 15px;')
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val, 1)
            sl.addLayout(row)
        if note:
            nlab = QLabel(f'Sipatlama: {note}')
            nlab.setWordWrap(True)
            nlab.setStyleSheet('color: #5F6368; margin-top: 6px;')
            sl.addWidget(nlab)
        self._sess_body.addWidget(stats)
        goods_card = _card()
        gl = QVBoxLayout(goods_card)
        gl.setContentsMargins(18, 14, 18, 14)
        orders = db.get_session_orders_grouped(sid, station)
        goods_orders = [o for o in orders if str(o.get('item_type') or '') != 'joystick']
        ghead = QHBoxLayout()
        gt = QLabel('Alg\'an tovarlari')
        gt.setStyleSheet('font-weight: 800; font-size: 14px;')
        ghead.addWidget(gt)
        badge = QLabel(str(len(goods_orders)))
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet('background: #E5E7EB; border-radius: 14px; font-weight: 800;')
        ghead.addWidget(badge)
        ghead.addStretch(1)
        gl.addLayout(ghead)
        if not goods_orders:
            empty = QLabel('Hesh nárse joq')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet('color: #9CA3AF; padding: 24px; font-size: 14px;')
            gl.addWidget(empty)
        else:
            for o in goods_orders:
                line = QHBoxLayout()
                nm = str(o.get('name') or '')
                cnt = int(o.get('count') or 0)
                tot = float(o.get('total') or 0)
                line.addWidget(QLabel(f'{nm} × {cnt}'))
                tv = QLabel(_fmt(tot))
                tv.setStyleSheet('color: #DC2626; font-weight: 800;')
                tv.setAlignment(Qt.AlignmentFlag.AlignRight)
                line.addWidget(tv, 1)
                gl.addLayout(line)
        self._sess_body.addWidget(goods_card)
        tot_card = _card()
        tl = QVBoxLayout(tot_card)
        tl.setContentsMargins(18, 14, 18, 14)
        for label, value, color in [('Tovarlar summasi', _fmt(goods), '#DC2626'), ('Uliwmaliq summa', _fmt(total), '#16A34A')]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            val = QLabel(value)
            val.setStyleSheet(f'color: {color}; font-weight: 900; font-size: 18px;')
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val, 1)
            tl.addLayout(row)
        self._sess_body.addWidget(tot_card)
        self._sess_body.addStretch(1)
        self.stack.setCurrentIndex(1)
    def _open_goods_edit(self) -> None:
        sid = int(self._edit_session_id or 0)
        station = self._edit_station_id or ''
        if sid <= 0 or not station:
            QMessageBox.warning(self, 'Diqqat', 'Seans tanlanmagan.')
            return
        else:
            dlg = SessionGoodsEditDialog(station, sid, self)
            dlg.exec()
            sess = db.get_session_by_id(sid)
            if sess:
                self._show_session(sess)
            self.reload()
            if self._on_changed:
                self._on_changed()
    def _edit_note(self, session_id: int, current: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle('Sipatlama')
        form = QFormLayout(dlg)
        edit = QLineEdit(current)
        form.addRow('Sipatlama:', edit)
        ok = QPushButton('Saqlaw')
        ok.clicked.connect(dlg.accept)
        form.addRow(ok)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            db.set_session_note(session_id, edit.text())
            sess = db.get_session_by_id(session_id)
            if sess:
                sess['drink_revenue'] = db.get_station_drink_total(str(sess.get('station_id') or ''), session_id)
                self._show_session(sess)
            self.reload()
    def _add_debt_from_session(self, station_label: str, amount: float) -> None:
        dlg = DebtorAddDialog(self)
        dlg.amount.setValue(max(1, int(amount)))
        dlg.note.setText(f'Seans: {station_label}')
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            try:
                db.add_debtor(dlg.name.text(), dlg.phone.text(), dlg.amount.value(), dlg.note.text())
                QMessageBox.information(self, 'OK', 'Qariz yozildi.')
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
    def _build_product_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet('background: #F5F6F8;')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 8, 16, 16)
        top = QHBoxLayout()
        crumb = QLabel('Jabilg\'an  >  Satilg\'an tovar mag\'liwmati')
        crumb.setStyleSheet('color: #5F6368; font-weight: 700;')
        top.addWidget(crumb, 1)
        back = QPushButton('← Artqa')
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        top.addWidget(back)
        outer.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self._prod_body = QVBoxLayout(body)
        self._prod_body.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        return page
    def _show_product(self, prod: dict[str, Any]) -> None:
        while self._prod_body.count():
            item = self._prod_body.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        head = _card()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(18, 16, 18, 16)
        title = QLabel(str(prod.get('name') or ''))
        title.setStyleSheet('font-size: 22px; font-weight: 900; color: #111827;')
        hl.addWidget(title)
        self._prod_body.addWidget(head)
        stock = _card()
        sl = QVBoxLayout(stock)
        sl.setContentsMargins(18, 14, 18, 14)
        for label, value, color in [('Baslang\'ish qaldiq', str(int(prod.get('start_stock') or 0)), '#111827'), ('Ha\'zirgi qaldiq', str(int(prod.get('stock') or 0)), '#111827'), ('Satilg\'an sani', str(int(prod.get('sold_count') or 0)), '#2563EB')]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            val = QLabel(value)
            val.setStyleSheet(f'color: {color}; font-weight: 800; font-size: 16px;')
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val, 1)
            sl.addLayout(row)
        self._prod_body.addWidget(stock)
        sales = db.list_product_sales(str(prod.get('raw_name') or ''), kind=str(prod.get('kind') or 'drink'), volume=float(prod.get('volume') or 0))
        groups = {}
        for s in sales:
            t = _hhmm(str(s.get('order_time') or ''))
            g = groups.setdefault(t, {'time': t, 'count': 0, 'total': 0.0})
            g['count'] += 1
            g['total'] += float(s.get('price') or 0)
        hist = _card()
        hl2 = QVBoxLayout(hist)
        hl2.setContentsMargins(18, 14, 18, 14)
        hrow = QHBoxLayout()
        ht = QLabel('Kassada satilg\'anlar')
        ht.setStyleSheet('font-weight: 800;')
        hrow.addWidget(ht)
        badge = QLabel(str(len(groups)))
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet('background: #E5E7EB; border-radius: 14px; font-weight: 800;')
        hrow.addWidget(badge)
        hrow.addStretch(1)
        hl2.addLayout(hrow)
        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(['Satiw waqti', 'Sani', 'Uliwmaliq summa'])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        rows = list(groups.values())
        tbl.setRowCount(len(rows))
        for i, g in enumerate(rows):
            tbl.setItem(i, 0, QTableWidgetItem(f"🕐  {g['time']}"))
            c = QTableWidgetItem(str(g['count']))
            c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            c.setForeground(QColor('#2563EB'))
            c.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
            tbl.setItem(i, 1, c)
            tot = QTableWidgetItem(_fmt(g['total']))
            tot.setForeground(QColor('#16A34A'))
            tot.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
            tot.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tbl.setItem(i, 2, tot)
        tbl.setMaximumHeight(min(280, 48 + 40 * max(1, len(rows))))
        hl2.addWidget(tbl)
        self._prod_body.addWidget(hist)
        price_card = _card()
        pl = QVBoxLayout(price_card)
        pl.setContentsMargins(18, 14, 18, 14)
        for label, value, color in [('Satiw baxasi', _fmt(float(prod.get('unit_price') or 0)), '#DC2626'), ('Satilg\'an summa', _fmt(float(prod.get('sold_total') or 0)), '#16A34A')]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            val = QLabel(value)
            val.setStyleSheet(f'color: {color}; font-weight: 900; font-size: 18px;')
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val, 1)
            pl.addLayout(row)
        self._prod_body.addWidget(price_card)
        self._prod_body.addStretch(1)
        self.stack.setCurrentIndex(2)
    def set_search(self, text: str) -> None:
        self._search = (text or '').strip().lower()
        self._apply_search()
    def reload(self) -> None:
        day = db.current_business_date().isoformat()
        self._sessions = db.sessions_breakdown_for_day(day)
        raw = db.sold_products_for_day(day)
        merged = {}
        for p in raw:
            key = (str(p.get('kind')), str(p.get('raw_name') or '').lower(), float(p.get('volume') or 0))
            if key not in merged:
                merged[key] = dict(p)
            else:
                m = merged[key]
                m['sold_count'] = int(m.get('sold_count') or 0) + int(p.get('sold_count') or 0)
                m['sold_total'] = float(m.get('sold_total') or 0) + float(p.get('sold_total') or 0)
                if m['sold_count']:
                    m['unit_price'] = m['sold_total'] / m['sold_count']
                m['start_stock'] = int(m.get('stock') or 0) + int(m.get('sold_count') or 0)
        self._products = list(merged.values())
        self._fill_sessions()
        self._fill_products()
        self._apply_search()
        if self.stack.currentIndex() != 0:
            return
    def _fill_sessions(self) -> None:
        self.sess_table.setRowCount(len(self._sessions))
        self.sess_table.verticalHeader().setDefaultSectionSize(44)
        for i, s in enumerate(self._sessions):
            sid = str(s.get('station_id') or '')
            try:
                name = db.get_station_display_name(sid)
            except Exception:
                name = sid
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, int(s.get('id') or 0))
            self.sess_table.setItem(i, 0, name_item)
            t_item = QTableWidgetItem(_hhmm(str(s.get('end_time') or '')))
            t_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sess_table.setItem(i, 1, t_item)
            tot = QTableWidgetItem(_fmt(float(s.get('revenue') or 0)))
            tot.setForeground(QColor('#16A34A'))
            tot.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
            tot.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.sess_table.setItem(i, 2, tot)
            self.sess_table.setItem(i, 3, QTableWidgetItem(str(s.get('note') or '')))
            goods_val = float(s.get('drink_revenue') or 0)
            goods = QTableWidgetItem(_fmt(goods_val))
            goods.setForeground(QColor('#DC2626'))
            goods.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
            goods.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.sess_table.setItem(i, 4, goods)
            ps_val = float(s.get('session_revenue') or 0) + float(s.get('joystick_revenue') or 0)
            if not ps_val:
                ps_val = max(0.0, float(s.get('revenue') or 0) - goods_val)
            ps = QTableWidgetItem(_fmt(ps_val))
            ps.setForeground(QColor('#2563EB'))
            ps.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
            ps.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.sess_table.setItem(i, 5, ps)
    def _fill_products(self) -> None:
        goods_sum = sum((float(p.get('sold_total') or 0) for p in self._products))
        self.prod_title.setText(f'Satilg\'an tovarlar {_fmt(goods_sum)}')
        self.prod_table.setRowCount(len(self._products))
        self.prod_table.verticalHeader().setDefaultSectionSize(56)
        for i, p in enumerate(self._products):
            self.prod_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.prod_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, i)
            img = QLabel()
            img.setFixedSize(48, 48)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            raw = p.get('image')
            if raw:
                pix = QPixmap()
                if pix.loadFromData(bytes(raw)) and (not pix.isNull()):
                    img.setPixmap(pix.scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    img.setText('—')
            else:
                img.setText('—')
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(2, 2, 2, 2)
            wl.addWidget(img)
            self.prod_table.setCellWidget(i, 1, wrap)
            self.prod_table.setItem(i, 2, QTableWidgetItem(str(p.get('name') or '')))
            c = QTableWidgetItem(str(int(p.get('sold_count') or 0)))
            c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.prod_table.setItem(i, 3, c)
            sm = QTableWidgetItem(_fmt(float(p.get('sold_total') or 0)))
            sm.setForeground(QColor('#16A34A'))
            sm.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
            self.prod_table.setItem(i, 4, sm)
            st = QTableWidgetItem(str(int(p.get('stock') or 0)))
            st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.prod_table.setItem(i, 5, st)
    def _apply_search(self) -> None:
        q = self._search
        for row in range(self.sess_table.rowCount()):
            hay = ' '.join((self.sess_table.item(row, c).text().lower() if self.sess_table.item(row, c) else '' for c in range(self.sess_table.columnCount())))
            self.sess_table.setRowHidden(row, bool(q and q not in hay))
        for row in range(self.prod_table.rowCount()):
            item = self.prod_table.item(row, 2)
            hay = item.text().lower() if item else ''
            self.prod_table.setRowHidden(row, bool(q and q not in hay))
    def _on_session_clicked(self, row: int, _col: int) -> None:
        item = self.sess_table.item(row, 0)
        if item is None:
            return
        sid = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        sess = next((s for s in self._sessions if int(s.get('id') or 0) == sid), None)
        if sess is None:
            if 0 <= row < len(self._sessions):
                    sess = self._sessions[row]
        if sess:
            self._show_session(sess)
    def _on_product_clicked(self, row: int, _col: int) -> None:
        item = self.prod_table.item(row, 0)
        idx = int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else row
        if idx < 0 or idx >= len(self._products):
            return None
        else:
            self._show_product(self._products[idx])
    def show_list(self) -> None:
        self.stack.setCurrentIndex(0)
        self.reload()