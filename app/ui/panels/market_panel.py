"""\nBoshqaruv paneli (to\'q mavzu):\n  - mode=\"drink\"  : Ichimliklar boshqaruvi (narx, son, rasm)\n  - mode=\"market\" : Yeydigan narsalar (market) boshqaruvi (narx, gramm, son, rasm)\n\nBosh ekrandagi yuqori menyudan ochiladi:\n  «Ichimliklar» -> mode=\"drink\",  «Market» -> mode=\"market\".\n"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout, QTabWidget, QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QAbstractItemView, QFileDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon
import database as db
BG_MAIN = '#FFFFFF'
BG_HEADER = '#F5F6F8'
BG_CARD = '#FFFFFF'
TEXT_PRIMARY = '#202124'
TEXT_SECONDARY = '#5F6368'
ACCENT = '#6B7C3B'
COL_GREEN = '#16A34A'
COL_RED = '#DC2626'
BORDER = '#E5E7EB'
_DARK_STYLE = f'\n    QDialog {{\n        background-color: {BG_MAIN};\n        color: {TEXT_PRIMARY};\n    }}\n    QLabel {{ color: {TEXT_PRIMARY}; }}\n    QTabWidget::pane {{\n        border: 1px solid {BORDER};\n        background: {BG_HEADER};\n        border-radius: 12px;\n        padding: 10px;\n    }}\n    QTabBar::tab {{\n        background: {BG_CARD};\n        border: 1px solid {BORDER};\n        border-top-left-radius: 8px;\n        border-top-right-radius: 8px;\n        padding: 12px 18px;\n        margin-right: 5px;\n        font-weight: bold;\n        color: {TEXT_SECONDARY};\n    }}\n    QTabBar::tab:selected {{\n        background: {ACCENT};\n        color: #FFFFFF;\n    }}\n    QLabel#Title {{\n        font-size: 22px;\n        font-weight: 900;\n        color: {ACCENT};\n        margin-bottom: 5px;\n    }}\n    QLabel#Summary {{\n        font-size: 15px;\n        font-weight: bold;\n        color: {COL_GREEN};\n        padding: 8px;\n        background: rgba(22,163,74,0.10);\n        border-radius: 8px;\n    }}\n    QGroupBox {{\n        background: {BG_HEADER};\n        border: 1px solid {BORDER};\n        border-radius: 12px;\n        font-size: 15px;\n        font-weight: bold;\n        margin-top: 20px;\n        padding-top: 20px;\n        color: {ACCENT};\n    }}\n    QGroupBox::title {{\n        subcontrol-origin: margin;\n        left: 12px;\n        padding: 0 6px;\n    }}\n    QPushButton {{\n        background-color: {ACCENT};\n        color: #FFFFFF;\n        font-weight: 900;\n        border: none;\n        border-radius: 8px;\n        padding: 12px;\n        font-size: 14px;\n    }}\n    QPushButton:hover {{ background-color: #5A6A32; }}\n    QPushButton#DeleteBtn {{\n        background: {COL_RED};\n        color: white;\n        padding: 5px;\n        font-size: 14px;\n    }}\n    QPushButton#ImgBtn {{\n        background: {BG_HEADER};\n        color: {TEXT_PRIMARY};\n        border: 1px solid {BORDER};\n        padding: 4px;\n    }}\n    QPushButton#ImgBtn:hover {{ border: 1px solid {ACCENT}; }}\n    QPushButton#StockAddBtn {{\n        background: {COL_GREEN};\n        color: #FFFFFF;\n        min-width: 140px;\n    }}\n    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{\n        background: {BG_CARD};\n        border: 1px solid {BORDER};\n        border-radius: 6px;\n        padding: 10px;\n        color: {TEXT_PRIMARY};\n        font-size: 14px;\n    }}\n    QComboBox:hover, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}\n    QComboBox QAbstractItemView {{\n        background-color: {BG_CARD};\n        color: {TEXT_PRIMARY};\n        selection-background-color: {ACCENT};\n        selection-color: #FFFFFF;\n        border: 1px solid {ACCENT};\n        outline: none;\n    }}\n    QTableWidget {{\n        background-color: {BG_CARD};\n        gridline-color: {BORDER};\n        border: 1px solid {BORDER};\n        color: {TEXT_PRIMARY};\n    }}\n    QHeaderView::section {{\n        background-color: {BG_HEADER};\n        color: {TEXT_PRIMARY};\n        padding: 8px;\n        border: 1px solid {BORDER};\n        font-weight: bold;\n    }}\n    QTableWidget::item {{\n        padding: 6px;\n        color: {TEXT_PRIMARY};\n    }}\n'
def _pick_image_bytes(parent) -> 'bytes | None':
    """Foydalanuvchidan rasm tanlab, baytlarini qaytaradi."""
    path, _ = QFileDialog.getOpenFileName(parent, 'Rasm tanlang', '', 'Rasmlar (*.png *.jpg *.jpeg *.bmp *.webp)')
    if not path:
        return None
    try:
        with open(path, 'rb') as f:
            return f.read()
    except Exception:
        return None
def _thumb_label(image_bytes, size: int=40) -> QLabel:
    lbl = QLabel()
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if image_bytes:
        pix = QPixmap()
        if pix.loadFromData(bytes(image_bytes)) and (not pix.isNull()):
            lbl.setPixmap(pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            return lbl
    lbl.setText('—')
    lbl.setStyleSheet(f'color: {TEXT_SECONDARY};')
    return lbl
class MarketPanelDialog(QDialog):
    """Ichimlik / Market boshqaruvi (yorug\' mavzu).\n\n    mode: \"drink\" | \"market\" | \"all\" (ichimlik + market birga)\n    sales_only: faqat sotish\n    preselect: BAR dan tanlangan mahsulot dict (kind/name/...)\n    """
    def __init__(self, parent=None, mode: str='drink', sales_only: bool=False, preselect: dict | None=None, with_market: bool=False):
        super().__init__(parent)
        mode = (mode or 'drink').strip().lower()
        if mode not in {'drink', 'market', 'all'}:
            mode = 'drink'
        self.mode = mode
        self._all_mode = mode == 'all' or bool(with_market)
        self._is_market = mode == 'market'
        self._sales_only = bool(sales_only)
        self._preselect = preselect or None
        self._pending_image = None
        self._pending_market_image = None
        self._active_list = 'drink'
        if self._preselect and self._preselect.get('kind') == 'market':
                self._is_market = True
        if self._all_mode:
            title_win = 'Ichimliklar / Market Markazi'
        else:
            if self._is_market:
                title_win = 'Market — Yeydigan narsalar'
            else:
                title_win = 'Ichimliklar Markazi'
        self.setWindowTitle(title_win)
        self.setMinimumSize(860, 780)
        self.setStyleSheet(_DARK_STYLE)
        main_layout = QVBoxLayout(self)
        if self._sales_only:
            if self._preselect and self._preselect.get('kind') == 'market':
                title_text = '🍔  MARKET — SOTISH'
            else:
                if self._all_mode or (self._preselect and self._preselect.get('kind') == 'drink'):
                    title_text = '🛒  SOTISH'
                else:
                    title_text = '🍔  MARKET — SOTISH' if self._is_market else '🥤  ICHIMLIK — SOTISH'
        else:
            title_text = '🥤  ICHIMLIKLAR / MARKET BOSHQARUVI' if self._all_mode else '🍔  MARKET BOSHQARUVI' if self._is_market else '🥤  ICHIMLIKLAR BOSHQARUVI'
        title = QLabel(title_text)
        title.setObjectName('Title')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        if self._sales_only:
            self.order_tab = QWidget()
            self.setup_order_tab(combined=True)
            main_layout.addWidget(self.order_tab)
            main_layout.addStretch()
        else:
            self.tabs = QTabWidget()
            self.order_tab = QWidget()
            self.setup_order_tab(combined=self._all_mode)
            self.tabs.addTab(self.order_tab, '🛒 SOTISH')
            self.drink_list_table = None
            self.market_list_table = None
            if self.mode in {'drink', 'all'} or self._all_mode:
                self._is_market = False
                self._active_list = 'drink'
                self.list_tab = QWidget()
                self.drink_list_tab = self.list_tab
                self.setup_list_tab()
                self.drink_list_table = self.list_table
                self.tabs.addTab(self.list_tab, '⚙️ ICHIMLIKLAR RO\'YXATI')
            if self.mode in {'market', 'all'} or self._all_mode:
                self._is_market = True
                self._active_list = 'market'
                self.market_list_tab = QWidget()
                self.list_tab = self.market_list_tab
                self.setup_list_tab()
                self.market_list_table = self.list_table
                self.tabs.addTab(self.market_list_tab, '⚙️ MARKET MAHSULOTLARI')
            if self.drink_list_table is not None:
                self._is_market = False
                self._active_list = 'drink'
                self.list_table = self.drink_list_table
            else:
                if self.market_list_table is not None:
                    self._is_market = True
                    self._active_list = 'market'
                    self.list_table = self.market_list_table
            self.stock_tab = QWidget()
            self.setup_stock_tab()
            self.tabs.addTab(self.stock_tab, '📦 SONI (OMBOR)')
            self.tabs.currentChanged.connect(self._on_tab_changed)
            main_layout.addWidget(self.tabs)
        self.load_data()
        self._apply_preselect()
    def _apply_preselect(self) -> None:
        if not self._preselect or not hasattr(self, 'order_item'):
            return None
        else:
            want_kind = str(self._preselect.get('kind') or 'drink')
            for i in range(self.order_item.count()):
                data = self.order_item.itemData(i)
                if not isinstance(data, dict):
                    continue
                else:
                    kind = str(data.get('kind') or ('market' if 'id' in data and 'drink_name' not in data else 'drink'))
                    if kind != want_kind:
                        continue
                    else:
                        if want_kind == 'drink':
                            if str(data.get('drink_name') or '') == str(self._preselect.get('drink_name') or '') and abs(float(data.get('volume') or 0) - float(self._preselect.get('volume') or 0)) < 1e-06:
                                self.order_item.setCurrentIndex(i)
                                return
                            else:
                                label = self.order_item.itemText(i).lower()
                                pname = str(self._preselect.get('name') or '').lower()
                                if pname and pname.split()[0] in label and (f"{float(self._preselect.get('volume') or 0):g}" in label.replace(',', '.')):
                                    self.order_item.setCurrentIndex(i)
                                    return
                        else:
                            if int(data.get('id') or 0) == int(self._preselect.get('id') or (-1)):
                                self.order_item.setCurrentIndex(i)
                                break
    def setup_order_tab(self, combined: bool=False):
        self._order_combined = bool(combined) or self._all_mode or self._sales_only
        layout = QVBoxLayout(self.order_tab)
        group = QGroupBox('Mijozga sotish (stolsiz ham)')
        form = QFormLayout()
        self.order_item = QComboBox()
        self.order_count = QSpinBox()
        self.order_count.setRange(1, 1000)
        label = '🛒 Mahsulotni tanlang:' if self._order_combined else '🍔 Mahsulotni tanlang:' if self._is_market else '🍹 Ichimlikni tanlang:'
        form.addRow(label, self.order_item)
        form.addRow('🔢 Soni:', self.order_count)
        self.btn_order = QPushButton('✅ SOTISH')
        self.btn_order.clicked.connect(self.submit_order)
        form.addRow(self.btn_order)
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
    def setup_list_tab(self):
        layout = QVBoxLayout(self.list_tab)
        if self._is_market:
            add_group = QGroupBox('➕ Yangi mahsulot qo\'shish')
            add_lay = QVBoxLayout()
            row1 = QHBoxLayout()
            self.new_name = QLineEdit()
            self.new_name.setPlaceholderText('Mahsulot nomi (masalan: Chipsi)')
            self.new_grams = QDoubleSpinBox()
            self.new_grams.setRange(0, 100000)
            self.new_grams.setDecimals(0)
            self.new_grams.setSingleStep(10)
            self.new_grams.setSuffix(' g')
            self.new_grams.setMinimumWidth(110)
            self.new_cost = QSpinBox()
            self.new_cost.setRange(0, 100000000)
            self.new_cost.setSuffix(' so\'m')
            self.new_cost.setMinimumWidth(120)
            self.new_cost.setToolTip('Keliw narxi — faqat ko\'rish uchun, hisobga ta\'sir qilmaydi')
            self.new_price = QSpinBox()
            self.new_price.setRange(0, 100000000)
            self.new_price.setSuffix(' so\'m')
            self.new_price.setMinimumWidth(130)
            row1.addWidget(self.new_name, 2)
            row1.addWidget(self.new_grams, 1)
            row1.addWidget(QLabel('K.NARXI'))
            row1.addWidget(self.new_cost, 1)
            row1.addWidget(self.new_price, 1)
            add_lay.addLayout(row1)
            row2 = QHBoxLayout()
            self.new_qty = QSpinBox()
            self.new_qty.setRange(0, 1000000)
            self.new_qty.setSuffix(' ta')
            self.btn_pick_img = QPushButton('🖼 Rasm tanlash')
            self.btn_pick_img.setObjectName('ImgBtn')
            self.btn_pick_img.clicked.connect(lambda _=False: self._pick_new_image(True))
            self.img_status = QLabel('Rasm tanlanmagan')
            self.img_status.setStyleSheet(f'color: {TEXT_SECONDARY};')
            btn_add = QPushButton('QO\'SHISH')
            btn_add.clicked.connect(lambda _=False: self.add_new_item(True))
            row2.addWidget(QLabel('Soni:'))
            row2.addWidget(self.new_qty)
            row2.addWidget(self.btn_pick_img)
            row2.addWidget(self.img_status, 1)
            row2.addWidget(btn_add)
            add_lay.addLayout(row2)
            add_group.setLayout(add_lay)
            layout.addWidget(add_group)
            self.list_table = QTableWidget()
            self.list_table.setColumnCount(7)
            self.list_table.setHorizontalHeaderLabels(['Rasm', 'Nomi', 'Gramm', 'K.NARXI', 'Narxi (so\'m)', 'Rasm o\'zgartirish', 'O\'chirish'])
            self.market_new_name = self.new_name
            self.market_new_grams = self.new_grams
            self.market_new_cost = self.new_cost
            self.market_new_price = self.new_price
            self.market_new_qty = self.new_qty
            self.market_img_status = self.img_status
        else:
            add_group = QGroupBox('➕ Yangi ichimlik qo\'shish')
            add_lay = QVBoxLayout()
            row1 = QHBoxLayout()
            self.new_name = QLineEdit()
            self.new_name.setPlaceholderText('Ichimlik nomi (masalan: Kola)')
            self.new_volume = QDoubleSpinBox()
            self.new_volume.setRange(0.1, 10.0)
            self.new_volume.setDecimals(2)
            self.new_volume.setSingleStep(0.25)
            self.new_volume.setValue(0.5)
            self.new_volume.setSuffix(' L')
            self.new_volume.setMinimumWidth(90)
            self.new_cost = QSpinBox()
            self.new_cost.setRange(0, 100000000)
            self.new_cost.setSuffix(' so\'m')
            self.new_cost.setMinimumWidth(120)
            self.new_cost.setToolTip('Keliw narxi — faqat ko\'rish uchun, hisobga ta\'sir qilmaydi')
            self.new_price = QSpinBox()
            self.new_price.setRange(0, 100000000)
            self.new_price.setSuffix(' so\'m')
            self.new_price.setMinimumWidth(120)
            row1.addWidget(self.new_name, 2)
            row1.addWidget(self.new_volume, 1)
            row1.addWidget(QLabel('K.NARXI'))
            row1.addWidget(self.new_cost, 1)
            row1.addWidget(self.new_price, 1)
            add_lay.addLayout(row1)
            row2 = QHBoxLayout()
            self.btn_pick_img = QPushButton('🖼 Rasm tanlash')
            self.btn_pick_img.setObjectName('ImgBtn')
            self.btn_pick_img.clicked.connect(lambda _=False: self._pick_new_image(False))
            self.img_status = QLabel('Rasm tanlanmagan')
            self.img_status.setStyleSheet(f'color: {TEXT_SECONDARY};')
            btn_add = QPushButton('QO\'SHISH')
            btn_add.clicked.connect(lambda _=False: self.add_new_item(False))
            row2.addWidget(self.btn_pick_img)
            row2.addWidget(self.img_status, 1)
            row2.addWidget(btn_add)
            add_lay.addLayout(row2)
            add_group.setLayout(add_lay)
            layout.addWidget(add_group)
            self.list_table = QTableWidget()
            self.list_table.setColumnCount(7)
            self.list_table.setHorizontalHeaderLabels(['Rasm', 'Nomi', 'Hajm (L)', 'K.NARXI', 'Narxi (so\'m)', 'Rasm o\'zgartirish', 'O\'chirish'])
            self.drink_new_name = self.new_name
            self.drink_new_volume = self.new_volume
            self.drink_new_cost = self.new_cost
            self.drink_new_price = self.new_price
            self.drink_img_status = self.img_status
        self.list_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.list_table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.list_table)
        is_m = self._is_market
        btn_save = QPushButton('💾 NARXLARNI SAQLASH')
        btn_save.clicked.connect(lambda _=False, m=is_m: self.save_prices(m))
        layout.addWidget(btn_save)
    def setup_stock_tab(self):
        layout = QVBoxLayout(self.stock_tab)
        layout.setSpacing(8)
        self.stock_summary = QLabel('')
        self.stock_summary.setObjectName('Summary')
        self.stock_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stock_summary)
        quick_group = QGroupBox('⚡ Tez qo\'shish (omborga)')
        quick_lay = QVBoxLayout()
        row1 = QHBoxLayout()
        self.stock_quick_item = QComboBox()
        self.stock_quick_item.setMinimumWidth(280)
        self.stock_quick_amount = QSpinBox()
        self.stock_quick_amount.setRange(1, 1000000)
        self.stock_quick_amount.setValue(1)
        self.stock_quick_amount.setSuffix(' ta')
        self.stock_quick_current = QLabel('Hozir: — ta')
        self.stock_quick_current.setStyleSheet(f'font-weight: bold; color: {ACCENT}; font-size: 15px; padding: 6px 12px; margin-left: 8px;')
        self.stock_quick_current.setMinimumWidth(140)
        self.stock_quick_item.currentIndexChanged.connect(self._update_quick_stock_label)
        btn_quick = QPushButton('➕ OMBORGA QO\'SHISH')
        btn_quick.setObjectName('StockAddBtn')
        btn_quick.clicked.connect(self.quick_add_stock)
        row1.addWidget(QLabel('Mahsulot:' if self._is_market else 'Ichimlik:'))
        row1.addWidget(self.stock_quick_item, 1)
        quick_lay.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(self.stock_quick_current)
        row2.addStretch(1)
        row2.addWidget(QLabel('Qo\'shish:'))
        row2.addWidget(self.stock_quick_amount)
        row2.addWidget(btn_quick)
        quick_lay.addLayout(row2)
        quick_group.setLayout(quick_lay)
        layout.addWidget(quick_group)
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(4)
        unit = 'Gramm' if self._is_market else 'Hajm (L)'
        self.stock_table.setHorizontalHeaderLabels(['Nomi', unit, 'Qoldiq (ta)', 'Holat'])
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.verticalHeader().setDefaultSectionSize(34)
        self.stock_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        layout.addWidget(self.stock_table)
        btn_save_stock = QPushButton('💾 BARCHA QOLDIQLARNI SAQLASH')
        btn_save_stock.clicked.connect(self.save_stock)
        layout.addWidget(btn_save_stock)
    def _on_tab_changed(self, index: int) -> None:
        if not hasattr(self, 'tabs'):
            return
        else:
            w = self.tabs.widget(index)
            if w is getattr(self, 'market_list_tab', None):
                self._is_market = True
                self._active_list = 'market'
                if self.market_list_table is not None:
                    self.list_table = self.market_list_table
            else:
                if w is getattr(self, 'drink_list_tab', None):
                    self._is_market = False
                    self._active_list = 'drink'
                    if self.drink_list_table is not None:
                        self.list_table = self.drink_list_table
            if w is self.stock_tab:
                self._load_stock_tab()
    def _stock_status(self, qty: int):
        if qty <= 0:
            return ('Tugagan', QColor('#FEE2E2'))
        else:
            if qty <= 5:
                return ('Kam', QColor('#FEF3C7'))
            else:
                return ('Yetarli', QColor('#DCFCE7'))
    def _pick_new_image(self, for_market: bool | None=None):
        data = _pick_image_bytes(self)
        if not data:
            return
        else:
            use_market = self._is_market if for_market is None else bool(for_market)
            if use_market:
                self._pending_market_image = data
                status = getattr(self, 'market_img_status', None) or getattr(self, 'img_status', None)
            else:
                self._pending_image = data
                status = getattr(self, 'drink_img_status', None) or getattr(self, 'img_status', None)
            if status is not None:
                status.setText('✅ Rasm tanlandi')
                status.setStyleSheet(f'color: {COL_GREEN};')
    def _items(self, for_market: bool | None=None):
        use_market = self._is_market if for_market is None else bool(for_market)
        return db.get_market_products() if use_market else db.get_drink_prices()
    def _stock_items(self):
        if self._all_mode:
            rows = []
            for d in db.get_drink_prices():
                row = dict(d)
                row['kind'] = 'drink'
                rows.append(row)
            for d in db.get_market_products():
                row = dict(d)
                row['kind'] = 'market'
                rows.append(row)
            return rows
        else:
            items = self._items()
            kind = 'market' if self._is_market else 'drink'
            out = []
            for d in items:
                row = dict(d)
                row['kind'] = kind
                out.append(row)
            return out
    def load_data(self):
        try:
            drinks = db.get_drink_prices()
            markets = db.get_market_products()
            self.order_item.clear()
            combined = getattr(self, '_order_combined', False) or self._all_mode or self._sales_only
            if combined:
                for d in drinks:
                    row = dict(d)
                    row['kind'] = 'drink'
                    vol = d.get('volume', 0.0)
                    qty = int(d.get('quantity', 0) or 0)
                    self.order_item.addItem(f"🥤 {d['drink_name']} ({vol:g}L) - {int(d['price'])} so\'m [{qty} ta]", row)
                for d in markets:
                    row = dict(d)
                    row['kind'] = 'market'
                    qty = int(d.get('quantity', 0) or 0)
                    self.order_item.addItem(f"🍔 {d['name']} ({float(d.get('grams', 0) or 0):g}g) - {int(d['price'])} so\'m [{qty} ta]", row)
            else:
                if self._is_market:
                    for d in markets:
                        row = dict(d)
                        row['kind'] = 'market'
                        qty = int(d.get('quantity', 0) or 0)
                        self.order_item.addItem(f"{d['name']} ({float(d.get('grams', 0) or 0):g}g) - {int(d['price'])} so\'m [{qty} ta]", row)
                else:
                    for d in drinks:
                        row = dict(d)
                        row['kind'] = 'drink'
                        vol = d.get('volume', 0.0)
                        qty = int(d.get('quantity', 0) or 0)
                        self.order_item.addItem(f"{d['drink_name']} ({vol:g}L) - {int(d['price'])} so\'m [{qty} ta]", row)
            if self._sales_only:
                self._apply_preselect()
                return
            else:
                if self.drink_list_table is not None:
                    self._fill_list_table(self.drink_list_table, drinks, is_market=False)
                if self.market_list_table is not None:
                    self._fill_list_table(self.market_list_table, markets, is_market=True)
                else:
                    if hasattr(self, 'list_table') and self.list_table is not None and (self.drink_list_table is None):
                                self._fill_list_table(self.list_table, markets if self._is_market else drinks, is_market=self._is_market)
                self._load_stock_tab()
                self._apply_preselect()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Yuklashda xato: {str(e)}')
    def _fill_list_table(self, table, items, *, is_market: bool) -> None:
        table.setRowCount(len(items))
        for i, d in enumerate(items):
            image = d.get('image')
            table.setCellWidget(i, 0, self._cell_center(_thumb_label(image)))
            if is_market:
                name = d['name']
                size_val = f"{float(d.get('grams', 0) or 0):g}"
            else:
                name = d['drink_name']
                size_val = f"{float(d.get('volume', 0.0)):g}"
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, name_item)
            size_item = QTableWidgetItem(size_val)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 2, size_item)
            cost_item = QTableWidgetItem(str(int(float(d.get('cost_price') or 0))))
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 3, cost_item)
            price_item = QTableWidgetItem(str(int(d['price'])))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 4, price_item)
            img_btn = QPushButton('🖼')
            img_btn.setObjectName('ImgBtn')
            img_btn.setFixedSize(40, 36)
            img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            img_btn.clicked.connect(lambda _=False, row=i, m=is_market: self._change_image_for(row, m))
            table.setCellWidget(i, 5, self._cell_center(img_btn))
            del_btn = QPushButton('🗑')
            del_btn.setObjectName('DeleteBtn')
            del_btn.setFixedSize(40, 36)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda _=False, row=i, m=is_market: self._delete_row_for(row, m))
            table.setCellWidget(i, 6, self._cell_center(del_btn))
    def _cell_center(self, widget) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.addWidget(widget)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setContentsMargins(0, 0, 0, 0)
        return w
    def _row_key(self, row: int, for_market: bool | None=None):
        """Jadval qatoridan mahsulot identifikatorini olish (qaytadan o\'qib)."""
        items = self._items(for_market)
        if row < 0 or row >= len(items):
            return None
        else:
            return items[row]
    def _change_image_for(self, row: int, for_market: bool):
        d = self._row_key(row, for_market)
        if not d:
            return
        else:
            data = _pick_image_bytes(self)
            if data is None:
                return
            else:
                try:
                    if for_market:
                        db.update_market_product(int(d['id']), image=data, update_image=True)
                    else:
                        db.set_drink_image(d['drink_name'], float(d['volume']), data)
                    QMessageBox.information(self, 'OK', 'Rasm yangilandi.')
                    self.load_data()
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', str(e))
    def change_image(self, row: int):
        self._change_image_for(row, self._is_market)
    def add_new_item(self, for_market: bool | None=None):
        use_market = self._is_market if for_market is None else bool(for_market)
        if use_market:
            name_w = getattr(self, 'market_new_name', None) or self.new_name
            name = name_w.text().strip()
        else:
            name_w = getattr(self, 'drink_new_name', None) or self.new_name
            name = name_w.text().strip()
        if not name:
            QMessageBox.warning(self, 'Xato', 'Nomi bo\'sh bo\'lishi mumkin emas!')
            return
        else:
            try:
                if use_market:
                    grams_w = getattr(self, 'market_new_grams', None) or self.new_grams
                    cost_w = getattr(self, 'market_new_cost', None) or getattr(self, 'new_cost', None)
                    price_w = getattr(self, 'market_new_price', None) or self.new_price
                    qty_w = getattr(self, 'market_new_qty', None) or self.new_qty
                    grams = float(grams_w.value())
                    cost = float(cost_w.value()) if cost_w is not None else 0.0
                    price = price_w.value()
                    qty = qty_w.value()
                    pending = self._pending_market_image
                    db.add_market_product(name=name, price=price, grams=grams, quantity=qty, image=pending, cost_price=cost)
                    self._pending_market_image = None
                    status = getattr(self, 'market_img_status', None)
                    if status is not None:
                        status.setText('Rasm tanlanmagan')
                        status.setStyleSheet(f'color: {TEXT_SECONDARY};')
                    grams_w.setValue(0)
                    if cost_w is not None:
                        cost_w.setValue(0)
                    qty_w.setValue(0)
                    msg = f'\'{name}\' qo\'shildi.'
                else:
                    vol_w = getattr(self, 'drink_new_volume', None) or self.new_volume
                    cost_w = getattr(self, 'drink_new_cost', None) or getattr(self, 'new_cost', None)
                    price_w = getattr(self, 'drink_new_price', None) or self.new_price
                    volume = float(vol_w.value())
                    cost = float(cost_w.value()) if cost_w is not None else 0.0
                    price = price_w.value()
                    db.set_drink_price(name, volume, price, cost_price=cost)
                    if self._pending_image:
                        db.set_drink_image(name, volume, self._pending_image)
                        self._pending_image = None
                        status = getattr(self, 'drink_img_status', None)
                        if status is not None:
                            status.setText('Rasm tanlanmagan')
                            status.setStyleSheet(f'color: {TEXT_SECONDARY};')
                    vol_w.setValue(0.5)
                    if cost_w is not None:
                        cost_w.setValue(0)
                    msg = f'\'{name}\' qo\'shildi.\nSonini «SONI (OMBOR)» bo\'limida kiriting.'
                name_w.clear()
                price_w.setValue(0)
                QMessageBox.information(self, 'Qo\'shildi', msg)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
    def _delete_row_for(self, row: int, for_market: bool):
        d = self._row_key(row, for_market)
        if not d:
            return
        else:
            name = d['name'] if for_market else d['drink_name']
            reply = QMessageBox.question(self, 'O\'chirish', f'Rostdan ham \'{name}\'ni o\'chirmoqchimisiz?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    if for_market:
                        db.delete_market_product(int(d['id']))
                    else:
                        db.delete_drink_price(d['drink_name'], float(d['volume']))
                    self.load_data()
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', str(e))
    def delete_row(self, row):
        self._delete_row_for(row, self._is_market)
    def save_prices(self, for_market: bool | None=None):
        use_market = self._is_market if for_market is None else bool(for_market)
        drink_t = getattr(self, 'drink_list_table', None)
        market_t = getattr(self, 'market_list_table', None)
        if use_market and market_t is not None:
            table = market_t
        else:
            if not use_market and drink_t is not None:
                table = drink_t
            else:
                table = self.list_table
        try:
            items = self._items(use_market)
            for i in range(table.rowCount()):
                if i >= len(items):
                    break
                else:
                    d = items[i]
                    try:
                        size_val = float(table.item(i, 2).text().strip())
                    except Exception:
                        size_val = float(d.get('grams', 0) if use_market else d.get('volume', 0.5))
                    try:
                        cost_val = float(table.item(i, 3).text().strip()) if table.item(i, 3) else 0.0
                    except Exception:
                        cost_val = float(d.get('cost_price') or 0)
                    try:
                        price = float(table.item(i, 4).text().strip())
                    except Exception:
                        continue
                    name = table.item(i, 1).text().strip()
                    if use_market:
                        db.update_market_product(int(d['id']), name=name, price=price, grams=size_val, cost_price=cost_val)
                    else:
                        db.set_drink_price(name, size_val, price, cost_price=cost_val)
            QMessageBox.information(self, 'OK', 'Narxlar saqlandi.')
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
    def _update_quick_stock_label(self) -> None:
        data = self.stock_quick_item.currentData()
        if not data:
            self.stock_quick_current.setText('Hozir: — ta')
            return
        else:
            kind = str(data.get('kind') or ('market' if self._is_market else 'drink'))
            if kind == 'market':
                qty = db.get_market_quantity(int(data['id']))
            else:
                qty = db.get_drink_quantity(data['drink_name'], data['volume'])
            self.stock_quick_current.setText(f'Hozir: {qty} ta')
    def _load_stock_tab(self) -> None:
        if not hasattr(self, 'stock_table'):
            return
        else:
            items = self._stock_items()
            total_units = 0
            empty_count = 0
            low_count = 0
            self.stock_quick_item.blockSignals(True)
            self.stock_quick_item.clear()
            for d in items:
                kind = str(d.get('kind') or 'drink')
                if kind == 'market':
                    label = f"🍔 {d['name']} ({float(d.get('grams', 0) or 0):g}g)"
                else:
                    label = f"🥤 {d['drink_name']} ({float(d.get('volume', 0.0)):g}L)"
                self.stock_quick_item.addItem(label, d)
            self.stock_quick_item.blockSignals(False)
            self._update_quick_stock_label()
            self.stock_table.setRowCount(len(items))
            for i, d in enumerate(items):
                kind = str(d.get('kind') or 'drink')
                if kind == 'market':
                    name = d['name']
                    size_val = f"{float(d.get('grams', 0) or 0):g}"
                else:
                    name = d['drink_name']
                    size_val = f"{float(d.get('volume', 0.0)):g}"
                qty = int(d.get('quantity', 0) or 0)
                total_units += qty
                if qty <= 0:
                    empty_count += 1
                else:
                    if qty <= 5:
                        low_count += 1
                name_item = QTableWidgetItem(name)
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.stock_table.setItem(i, 0, name_item)
                size_item = QTableWidgetItem(size_val)
                size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.stock_table.setItem(i, 1, size_item)
                qty_item = QTableWidgetItem(str(qty))
                qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                qty_item.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
                qty_item.setForeground(QColor(TEXT_PRIMARY))
                self.stock_table.setItem(i, 2, qty_item)
                status_text, bg = self._stock_status(qty)
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setBackground(bg)
                status_item.setForeground(QColor(TEXT_PRIMARY))
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.stock_table.setItem(i, 3, status_item)
            self.stock_summary.setText(f'📊 Jami omborda: {total_units} ta  |  ⚠️ Kam qolgan: {low_count}  |  ❌ Tugagan: {empty_count}')
    def quick_add_stock(self) -> None:
        data = self.stock_quick_item.currentData()
        amount = self.stock_quick_amount.value()
        if not data or amount <= 0:
            return None
        else:
            try:
                kind = str(data.get('kind') or ('market' if self._is_market else 'drink'))
                if kind == 'market':
                    old_qty = int(db.get_market_quantity(int(data['id'])) or 0)
                    new_total = db.add_market_stock(int(data['id']), amount)
                    name = str(data.get('name') or 'Mahsulot')
                    grams = float(data.get('grams') or 0)
                    if grams > 0 and f'{grams:g}' not in name:
                            name = f'{name} {grams:g} gr'
                else:
                    vol = float(data['volume'])
                    old_qty = int(db.get_drink_quantity(data['drink_name'], vol) or 0)
                    new_total = db.add_drink_stock(data['drink_name'], vol, amount)
                    name = str(data.get('drink_name') or 'Ichimlik')
                    if vol:
                        name = f'{name} {vol:g} L'
                tg_note = ''
                try:
                    from app.services.telegram_notify import notify_stock_changes_async
                    st = notify_stock_changes_async([{'name': name, 'old': old_qty, 'new': int(new_total)}])
                    if st == 'queued':
                        tg_note = '\nTelegramga xabar yuborilmoqda.'
                    else:
                        if st == 'not_configured':
                            tg_note = '\nTelegram sozlanmagan (Admin → TELEGRAM).'
                except Exception as e:
                    tg_note = f'\nTelegram xato: {e}'
                QMessageBox.information(self, 'Qo\'shildi', f'{name}\n+{amount} ta qo\'shildi.\nYangi qoldiq: {new_total} ta{tg_note}')
                self.stock_quick_amount.setValue(1)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
    def save_stock(self) -> None:
        try:
            items = self._stock_items()
            updated = 0
            changes = []
            for i in range(self.stock_table.rowCount()):
                if i >= len(items):
                    break
                else:
                    d = items[i]
                    qty_item = self.stock_table.item(i, 2)
                    if not qty_item:
                        continue
                    else:
                        try:
                            final_qty = max(0, int(qty_item.text().strip() or 0))
                        except ValueError:
                            continue
                        kind = str(d.get('kind') or ('market' if self._is_market else 'drink'))
                        if kind == 'market':
                            old_qty = int(db.get_market_quantity(int(d['id'])) or 0)
                            if old_qty == final_qty:
                                continue
                            else:
                                db.set_market_quantity(int(d['id']), final_qty)
                                name = str(d.get('name') or 'Mahsulot')
                                grams = float(d.get('grams') or 0)
                                if grams > 0 and f'{grams:g}' not in name:
                                        name = f'{name} {grams:g} gr'
                        else:
                            vol = float(d['volume'])
                            old_qty = int(db.get_drink_quantity(d['drink_name'], vol) or 0)
                            if old_qty == final_qty:
                                continue
                            else:
                                db.set_drink_quantity(d['drink_name'], vol, final_qty)
                                name = str(d.get('drink_name') or 'Ichimlik')
                                if vol:
                                    name = f'{name} {vol:g} L'
                        changes.append({'name': name, 'old': old_qty, 'new': final_qty})
                        updated += 1
            tg_note = ''
            if changes:
                try:
                    from app.services.telegram_notify import notify_stock_changes_async
                    st = notify_stock_changes_async(changes)
                    if st == 'queued':
                        tg_note = '\nTelegramga xabar yuborilmoqda.'
                    else:
                        if st == 'not_configured':
                            tg_note = '\nTelegram sozlanmagan (Admin → TELEGRAM).'
                except Exception as e:
                    tg_note = f'\nTelegram xato: {e}'
            QMessageBox.information(self, 'Saqlandi', f'{updated} ta mahsulot qoldig\'i yangilandi.{tg_note}')
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
    def submit_order(self):
        try:
            data = self.order_item.currentData()
            count = self.order_count.value()
            if not data:
                return
            kind = str(data.get('kind') or ('market' if self._is_market else 'drink'))
            if kind == 'market':
                available = db.get_market_quantity(int(data['id']))
                if available < count:
                    QMessageBox.warning(self, 'Omborda yetarli emas', f"'{data['name']}' uchun faqat {available} ta qolgan.")
                    return
                db.add_market_order(db.WALKIN_STATION_ID, int(data['id']), session_id=None, count=count)
                name = data['name']
                price = int(data['price'])
            else:
                available = db.get_drink_quantity(data['drink_name'], data['volume'])
                if available < count:
                    QMessageBox.warning(self, 'Omborda yetarli emas', f"'{data['drink_name']}' ({data['volume']:g}L) uchun faqat {available} ta qolgan.")
                    return
                for _ in range(count):
                    db.add_drink_order(db.WALKIN_STATION_ID, data['drink_name'], data['volume'], data['price'], session_id=None)
                name = data['drink_name']
                price = int(data['price'])
            total_price = price * count
            QMessageBox.information(self, 'OK', f"{count} ta {name} sotildi.\nSumma: {total_price:,} so'm (bugungi daromadga qo'shildi)")
            self.load_data()
            top = self.window()
            if hasattr(top, '_refresh_today_revenue_banner'):
                top._refresh_today_revenue_banner()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
