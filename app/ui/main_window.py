"""Modular PyQt asosiy oyna — Material sidebar + service qatlami."""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Dict, Optional
from PyQt6.QtCore import Qt, QTimer, QSize, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QFrame, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QApplication, QComboBox
from app.core.container import AppContainer
from app.core.paths import resource_path
from app.ui.pages.presenter import PagePresenter
from app.ui.theme import ACCENT, BG_MAIN, COL_RED, GOLD, TEXT_PRIMARY
from app.ui.widgets.grid_helpers import grid_layout_for_count as _grid_layout_for_count, right_cluster_width as _right_cluster_width, station_col_widths as _station_col_widths
from app.ui.widgets.admin_button import AdminButtonWidget as _AdminButtonWidget
from app.ui.widgets.product_card import ProductCard
from app.ui.widgets.station_card import StationCard
from app.ui.panels.cash_close_page import CashClosePage
from app.ui.panels.balance_page import BalancePage
from app.ui.dialogs import CustomerDisplayWindow, DebtorAddDialog, PasswordChangeDialog, TVSettingsDialog
logger = logging.getLogger(__name__)
class _ZakazBridge(QObject):
    """HTTP thread → UI thread."""
    called = pyqtSignal(int)
PAGE_TITLES = {'stations': 'Stollar', 'active': 'Jabilg\'an', 'bar': 'BAR', 'booking': 'Bronlaw', 'cash': 'Kassa jabıw', 'click': 'CLICK', 'cash_diff': 'Kassa parqi', 'warehouse': 'Sklad', 'debtors': 'Qarizdarlar', 'balance': 'Balans', 'expenses': 'Qa\'rejetler', 'clients': 'Klientler', 'about': 'Haqqında'}
class MainWindow(QMainWindow):
    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container
        self._presenter = PagePresenter(container)
        self._current_page = 'stations'
        self._nav_buttons = {}
        self._page_tables = {}
        self._page_index = {}
        self._cards = {}
        self._bar_cards = []
        self._bar_grid = None
        self._bar_reorder_mode = False
        self._bar_reorder_first = None
        self._bar_products = []
        self._bar_reorder_banner = None
        self._bar_page_root = None
        self._license_blocked = False
        self.setWindowTitle('Eagle Playstation')
        self.setGeometry(0, 0, 1920, 1080)
        logo_path = resource_path('ps_logo.png')
        if logo_path and logo_path.exists():
                self.setWindowIcon(QIcon(str(logo_path)))
        self._build_shell()
        self._populate_station_grid(wake_restored_tvs=True)
        self._customer_display = CustomerDisplayWindow()
        self._show_customer_display()
        self._zakaz_bridge = _ZakazBridge(self)
        self._zakaz_bridge.called.connect(self._on_zakaz)
        self.restart_zakaz_server()
        self._set_page('stations')
        self.showMaximized()
        self._start_timers()
    def _build_shell(self) -> None:
        central = QWidget()
        central.setObjectName('MainCentral')
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName('Sidebar')
        sidebar.setFixedWidth(250)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 8, 0, 8)
        side_lay.setSpacing(2)
        root.addWidget(sidebar)
        brand = QWidget()
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(16, 8, 14, 14)
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(38, 38)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = resource_path('ps_logo.png')
        if logo_path and logo_path.exists():
                pix = QPixmap(str(logo_path))
                if not pix.isNull():
                    logo_lbl.setPixmap(pix.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if logo_lbl.pixmap() is None:
            logo_lbl.setText('E')
            logo_lbl.setStyleSheet(f'background:{ACCENT};color:#FFF;border-radius:19px;font-weight:900;')
        brand_lay.addWidget(logo_lbl)
        brand_lay.addWidget(QLabel('Eagle Playstation'), 1)
        side_lay.addWidget(brand)
        self._nav_icons = {'stations': '⚙', 'active': '◎', 'bar': '☕', 'booking': '◷', 'cash': '▦', 'click': '💳', 'cash_diff': '⇄', 'warehouse': '▣', 'debtors': '⌂', 'balance': '$', 'expenses': '♙', 'clients': '⚭', 'about': 'ⓘ'}
        nav = [('stations', 'Stollar (0)'), ('active', 'Jabilg\'an'), ('bar', 'BAR'), ('booking', 'Bronlaw (0)'), ('cash', 'Kassa jabıw'), ('click', 'CLICK'), ('cash_diff', 'Kassa parqi'), ('warehouse', 'Sklad'), ('debtors', 'Qarizdarlar'), ('balance', 'Balans'), ('expenses', 'Qa\'rejetler'), ('clients', 'Klientler')]
        for key, text in nav:
            btn = self._sidebar_btn(self._nav_icons[key], text, key)
            self._nav_buttons[key] = btn
            side_lay.addWidget(btn)
        side_lay.addSpacing(8)
        self._btn_admin = _AdminButtonWidget()
        self._btn_admin._btn.setText('⚙  Admin')
        self._btn_admin._btn.setStyleSheet(self._sidebar_css(False))
        self._btn_admin.clicked.connect(self._open_admin)
        side_lay.addWidget(self._btn_admin)
        about = self._sidebar_btn('ⓘ', 'Haqqında', 'about')
        self._nav_buttons['about'] = about
        side_lay.addWidget(about)
        side_lay.addStretch()
        content = QWidget()
        content.setObjectName('Content')
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        root.addWidget(content, 1)
        self._today_revenue = QLabel()
        self._today_revenue.setTextFormat(Qt.TextFormat.RichText)
        appbar = QWidget()
        appbar.setObjectName('AppBar')
        bar_lay = QHBoxLayout(appbar)
        bar_lay.setContentsMargins(14, 8, 14, 8)
        self._page_heading = QLabel('Stollar')
        bar_lay.addWidget(self._page_heading)
        bar_lay.addStretch()
        self._search = QLineEdit()
        self._search.setObjectName('GlobalSearch')
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(430)
        self._search.textChanged.connect(self._on_search)
        bar_lay.addWidget(self._search)
        self._clock_label = QLabel()
        bar_lay.addWidget(self._clock_label)
        self._btn_refresh_revenue = QPushButton('🔄')
        self._btn_refresh_revenue.setToolTip('Daromadni yangilash (yopilgan stollar)')
        self._btn_refresh_revenue.setFixedSize(40, 36)
        self._btn_refresh_revenue.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh_revenue.setStyleSheet('QPushButton{background:#FEF3C7;color:#92400E;border:1px solid #F59E0B;border-radius:10px;font-size:16px;font-weight:900;}QPushButton:hover{background:#FDE68A;}QPushButton:pressed{background:#FBBF24;}')
        self._btn_refresh_revenue.clicked.connect(self._on_refresh_revenue_clicked)
        bar_lay.addWidget(self._btn_refresh_revenue)
        bar_lay.addWidget(self._today_revenue)
        content_lay.addWidget(appbar)
        titlebar = QWidget()
        title_lay = QHBoxLayout(titlebar)
        title_lay.setContentsMargins(14, 10, 14, 8)
        self._content_title = QLabel('Stollar (0)')
        title_lay.addWidget(self._content_title)
        title_lay.addStretch()
        self._primary_action = QPushButton('+ Qo\'sıw')
        self._primary_action.setObjectName('PrimaryAction')
        self._primary_action.clicked.connect(self._primary_action_clicked)
        title_lay.addWidget(self._primary_action)
        content_lay.addWidget(titlebar)
        self._stack = QStackedWidget()
        content_lay.addWidget(self._stack, 1)
        self._build_pages()
        self._apply_styles()
        self._refresh_revenue_banner()
    def _build_pages(self) -> None:
        stations = QWidget()
        lay = QVBoxLayout(stations)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._column_header())
        scroll = QScrollArea()
        scroll.setObjectName('StationsScroll')
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self._grid = QGridLayout(inner)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        self._footer_widget = QWidget()
        footer = QHBoxLayout(self._footer_widget)
        self._footer_logo = QLabel()
        footer.addWidget(self._footer_logo)
        lay.addWidget(self._footer_widget)
        self._add_page('stations', stations)
        from app.ui.panels.closed_sessions_page import ClosedSessionsPage
        self._closed_page = ClosedSessionsPage(self)
        self._add_page('active', self._closed_page)
        self._add_page('bar', self._bar_page())
        from app.ui.panels.bookings_page import BookingsPage
        self._bookings_page = BookingsPage(self, on_changed=lambda: (self._apply_bookings_to_cards(), self._update_sidebar_counts()))
        self._add_page('booking', self._bookings_page)
        self._cash_page = CashClosePage(self, on_cancel=lambda: self._set_page('stations'), on_saved=lambda: (self._refresh_revenue_banner(), getattr(self, '_cash_diff_page', None) and self._cash_diff_page.reload()))
        self._add_page('cash', self._cash_page)
        from app.ui.panels.click_page import ClickPage
        self._click_page = ClickPage(self)
        self._add_page('click', self._click_page)
        from app.ui.panels.cash_diff_page import CashDiffPage
        self._cash_diff_page = CashDiffPage(self)
        self._add_page('cash_diff', self._cash_diff_page)
        from app.ui.panels.warehouse_page import WarehousePage
        self._warehouse_page = WarehousePage(self)
        self._add_page('warehouse', self._warehouse_page)
        from app.ui.panels.debtors_page import DebtorsPage
        self._debtors_page = DebtorsPage(self, on_changed=lambda: self._update_sidebar_counts())
        self._add_page('debtors', self._debtors_page)
        self._balance_page_widget = BalancePage(self)
        self._add_page('balance', self._balance_page_widget)
        from app.ui.panels.expenses_page import ExpensesPage
        self._expenses_page = ExpensesPage(self, on_changed=lambda: self._update_sidebar_counts())
        self._add_page('expenses', self._expenses_page)
        from app.ui.panels.clients_page import ClientsPage
        self._clients_page = ClientsPage(self, on_changed=lambda: self._update_sidebar_counts())
        self._add_page('clients', self._clients_page)
        self._add_page('about', self._about_page())
    def _add_page(self, key: str, page: QWidget) -> None:
        self._page_index[key] = self._stack.addWidget(page)
    def _empty_page(self, text: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        return page
    def _table_page(self, key: str, headers: list[str]) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(table)
        self._page_tables[key] = table
        return page
    def _bar_page(self) -> QWidget:
        """BAR katalog — rasmdagi kabi rasmli mahsulot kartochkalari."""
        page = QWidget()
        page.setObjectName('BarPage')
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._bar_page_root = lay
        banner = QLabel()
        banner.setVisible(False)
        banner.setWordWrap(True)
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setStyleSheet('background: #FEF3C7; color: #92400E; font-weight: 800; padding: 10px 12px; border-bottom: 1px solid #F59E0B;')
        self._bar_reorder_banner = banner
        lay.addWidget(banner)
        scroll = QScrollArea()
        scroll.setObjectName('BarScroll')
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName('BarViewport')
        self._bar_grid = QGridLayout(inner)
        self._bar_grid.setContentsMargins(18, 14, 18, 18)
        self._bar_grid.setHorizontalSpacing(14)
        self._bar_grid.setVerticalSpacing(14)
        self._bar_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page
    def _reload_bar_grid(self) -> None:
        if self._bar_grid is None:
            return
        else:
            while self._bar_grid.count():
                item = self._bar_grid.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            self._bar_cards.clear()
            products = self._container.inventory.all_products_for_display()
            self._bar_products = list(products)
            cols = 7
            for i, p in enumerate(products):
                card = ProductCard(str(p.get('name') or ''), p.get('image'), price=float(p.get('price') or 0), purchase=float(p.get('purchase') or 0), quantity=int(p.get('quantity') or 0))
                card.clicked.connect(lambda _=False, prod=p: self._on_bar_card_clicked(prod))
                card.set_image_requested.connect(lambda prod=p: self._set_bar_product_image(prod))
                card.reorder_requested.connect(lambda: self._toggle_bar_reorder_mode())
                card.set_reorder_mode(self._bar_reorder_mode, selected=bool(self._bar_reorder_first and self._bar_product_key(self._bar_reorder_first) == self._bar_product_key(p)))
                self._bar_cards.append(card)
                self._bar_grid.addWidget(card, i // cols, i % cols)
            self._content_title.setText(f'BAR ({len(products)})')
            self._update_bar_reorder_banner()
            self._on_search(self._search.text())
    @staticmethod
    def _bar_product_key(product: dict) -> str:
        from app.db import legacy
        return legacy.module().bar_product_key(product)
    def _toggle_bar_reorder_mode(self) -> None:
        self._bar_reorder_mode = not self._bar_reorder_mode
        self._bar_reorder_first = None
        self._update_bar_reorder_banner()
        for i, card in enumerate(self._bar_cards):
            prod = self._bar_products[i] if i < len(self._bar_products) else None
            card.set_reorder_mode(self._bar_reorder_mode, selected=False)
        if self._bar_reorder_mode:
            QMessageBox.information(self, 'Joyini o\'zgartirish', 'BAR tartibini o\'zgartirish yoqildi.\n1) Birinchi tovarni bosing\n2) O\'rnini almashtirmoqchi bo\'lgan ikkinchi tovarni bosing.\n\nYana o\'ng tugmani ikki marta bosib rejimni o\'chirasiz.')
    def _update_bar_reorder_banner(self) -> None:
        if self._bar_reorder_banner is None:
            return
        else:
            if not self._bar_reorder_mode:
                self._bar_reorder_banner.setVisible(False)
                return
            else:
                if self._bar_reorder_first:
                    name = str(self._bar_reorder_first.get('name') or '')
                    self._bar_reorder_banner.setText(f'Joyini o\'zgartirish: «{name}» tanlandi — endi ikkinchi tovarni bosing. (O\'ng tugma ×2 = rejimni yopish)')
                else:
                    self._bar_reorder_banner.setText('Joyini o\'zgartirish rejimi: avval birinchi, so\'ng ikkinchi tovarni bosing. (O\'ng tugma ×2 = yopish)')
                self._bar_reorder_banner.setVisible(True)
    def _on_bar_card_clicked(self, product: dict) -> None:
        if self._bar_reorder_mode:
            if self._bar_reorder_first is None:
                self._bar_reorder_first = dict(product)
                self._update_bar_reorder_banner()
                key = self._bar_product_key(product)
                for i, card in enumerate(self._bar_cards):
                    prod = self._bar_products[i] if i < len(self._bar_products) else {}
                    card.set_reorder_mode(True, selected=self._bar_product_key(prod) == key)
            else:
                first = self._bar_reorder_first
                self._bar_reorder_first = None
                if self._bar_product_key(first) == self._bar_product_key(product):
                    self._update_bar_reorder_banner()
                    for card in self._bar_cards:
                        card.set_reorder_mode(True, selected=False)
                    return None
                else:
                    try:
                        self._container.inventory.swap_bar_products(first, product)
                        self._reload_bar_grid()
                    except Exception as e:
                        QMessageBox.critical(self, 'Xatolik', str(e))
                    return None
        else:
            if not product.get('image'):
                self._set_bar_product_image(product)
            else:
                self._open_market('all', sales_only=True, preselect=product)
    def _set_bar_product_image(self, product: dict) -> None:
        from app.ui.panels.market_panel import _pick_image_bytes
        data = _pick_image_bytes(self)
        if not data:
            return
        else:
            try:
                self._container.inventory.set_product_image(product, data)
                self._reload_bar_grid()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Rasm saqlanmadi:\n{e}')
    def _about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(QLabel('Eagle Playstation — modular boshqaruv tizimi'))
        row = QHBoxLayout()
        b_tv = QPushButton('📺 TV sozlamalari')
        b_tv.clicked.connect(self._open_tv_settings)
        b_parol = QPushButton('🔒 Parol')
        b_parol.clicked.connect(self._open_password)
        row.addWidget(b_tv)
        row.addWidget(b_parol)
        lay.addLayout(row)
        return page
    def _open_tv_settings(self) -> None:
        """TV sozlamalari ochiqda re-block timerlari to\'xtaydi — dialog qotmasin."""
        paused = []
        for name in ['_persistent_block_timer', '_vidaa_timer']:
            t = getattr(self, name, None)
            if t is not None and t.isActive():
                    t.stop()
                    paused.append(name)
        try:
            TVSettingsDialog(self).exec()
        finally:
            for name in paused:
                pass
            t = getattr(self, name, None)
            if t is not None:
                t.start()
    def _open_password(self) -> None:
        PasswordChangeDialog(self).exec()
    def _column_header(self) -> QWidget:
        _cols, compact = _grid_layout_for_count(len(self._container.stations.list_station_ids()))
        cw = _station_col_widths(compact)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(22, 6, 20, 4)
        def h(text: str, width: int=0, expand: bool=False) -> QLabel:
            lbl = QLabel(text)
            if expand:
                from PyQt6.QtWidgets import QSizePolicy
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            else:
                lbl.setFixedWidth(width)
            return lbl
        lay.addWidget(h('STOL', cw['stol']))
        lay.addWidget(h('HOLAT', cw['holat']))
        for title in ['BOSHLANGAN', 'O\'YNAGAN', 'PLAYSTATION', 'TOVARLAR', 'UMUMIY']:
            lay.addWidget(h(title, expand=True), 1)
        spacer = QWidget()
        spacer.setFixedWidth(_right_cluster_width(compact))
        lay.addWidget(spacer)
        return w
    def _sidebar_btn(self, icon: str, text: str, key: str) -> QPushButton:
        btn = QPushButton(f'{icon}  {text}')
        btn.setMinimumHeight(42)
        btn.setStyleSheet(self._sidebar_css(False))
        btn.clicked.connect(lambda _=False, k=key: self._set_page(k))
        return btn
    def _sidebar_css(self, selected: bool) -> str:
        bg = '#F1F4EC' if selected else '#FFFFFF'
        weight = '800' if selected else '600'
        return (
            f'QPushButton{{background:{bg};color:#202124;border:none;text-align:left;'
            f'padding:10px 16px;font-size:13px;font-weight:{weight};}}'
            f'QPushButton:hover{{background:#F6F7F3;}}'
        )
    def _apply_styles(self) -> None:
        self.setStyleSheet(f'\n            QWidget#MainCentral, QWidget#Content {{ background:{BG_MAIN}; }}\n            QWidget#Sidebar {{ background:#FFF; border-right:1px solid #E6E6E6; }}\n            QWidget#AppBar {{ background:#FFF; border-bottom:1px solid #E6E6E6; }}\n            QLineEdit#GlobalSearch {{ background:#F1F3F4; border:none; border-radius:3px; padding:9px 14px; }}\n            QPushButton#PrimaryAction {{ background:{ACCENT}; color:#FFF; border:none; border-radius:3px; padding:8px 14px; font-weight:700; }}\n            QPushButton#IconAction {{ background:#FFF; border:1px solid #E0E0E0; border-radius:3px; padding:8px 10px; }}\n            QScrollArea#StationsScroll, QScrollArea#BarScroll {{ border:none; background:transparent; }}\n            QWidget#BarPage, QWidget#BarViewport {{ background:#F5F5F5; }}\n            ')
    def _set_page(self, key: str) -> None:
        self._current_page = key
        self._stack.setCurrentIndex(self._page_index[key])
        title = PAGE_TITLES.get(key, key)
        self._page_heading.setText(title)
        self._content_title.setText(title)
        self._search.setPlaceholderText(f'Izlew {title}')
        for k, btn in self._nav_buttons.items():
            btn.setStyleSheet(self._sidebar_css(k == key))
        self._primary_action.setVisible(key not in {'click', 'cash', 'stations', 'cash_diff', 'active', 'balance', 'about'})
        self._refresh_current_page()
    def _refresh_current_page(self) -> None:
        key = self._current_page
        if key == 'stations':
            self._content_title.setText(f'Stollar ({len(self._cards)})')
        else:
            if key == 'active':
                self._closed_page.set_search(self._search.text())
                self._closed_page.reload()
                self._content_title.setText('Jabilg\'an')
            else:
                if key == 'bar':
                    self._reload_bar_grid()
                else:
                    if key == 'cash':
                        self._cash_page.reload()
                        self._content_title.setText('Kassa jabıw')
                    else:
                        if key == 'click':
                            self._click_page.reload()
                            self._content_title.setText('CLICK')
                        else:
                            if key == 'cash_diff':
                                self._cash_diff_page.apply_search(self._search.text())
                                self._cash_diff_page.reload()
                                self._content_title.setText(f'Kassa parqi ({self._cash_diff_page.table.rowCount()})')
                            else:
                                if key == 'warehouse':
                                    products = self._container.inventory.all_products_for_display()
                                    self._warehouse_page.set_products(products)
                                    self._warehouse_page.apply_search(self._search.text())
                                    self._content_title.setText(f'Sklad ({len(products)})')
                                else:
                                    if key == 'debtors':
                                        self._debtors_page.set_search(self._search.text())
                                        self._debtors_page.reload()
                                        self._content_title.setText('Qarizdarlar')
                                    else:
                                        if key == 'booking':
                                            self._bookings_page.set_search(self._search.text())
                                            self._bookings_page.reload()
                                            n = len(self._container.finance.bookings(self._search.text()))
                                            self._content_title.setText(f'Bronlaw ({n})')
                                        else:
                                            if key == 'expenses':
                                                self._expenses_page.set_search(self._search.text())
                                                self._expenses_page.reload()
                                                self._content_title.setText(f'Qa\'rejetler ({self._expenses_page.row_count()})')
                                            else:
                                                if key == 'clients':
                                                    self._clients_page.set_search(self._search.text())
                                                    self._clients_page.reload()
                                                    self._content_title.setText(f'Klientler ({self._clients_page.table.rowCount()})')
                                                else:
                                                    if key == 'balance':
                                                        bal = self._presenter.balance()
                                                        self._balance_page_widget.set_values(bal['total'], bal['safe'], bal['cash'])
        if key == 'stations':
            self._apply_bookings_to_cards()
        self._update_sidebar_counts()
        self._on_search(self._search.text())
    def _fill_table(self, key: str, rows: list[list[object]]) -> None:
        table = self._page_tables.get(key)
        if not table:
            return
        else:
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    if isinstance(val, (int, float)) and c > 0:
                            item.setText(f'{float(val):,.0f}')
                            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(r, c, item)
    def _on_search(self, text: str) -> None:
        q = (text or '').strip().lower()
        if self._current_page == 'stations':
            for card in self._cards.values():
                card.setVisible(not q or q in card.display_name().lower() or q in card.station_id.lower())
        else:
            if self._current_page == 'bar':
                for card in self._bar_cards:
                    card.setVisible(not q or q in card.display_name().lower())
            else:
                if self._current_page == 'debtors':
                    self._debtors_page.set_search(text)
                else:
                    if self._current_page == 'expenses':
                        self._expenses_page.set_search(text)
                    else:
                        if self._current_page == 'clients':
                            self._clients_page.set_search(text)
                        else:
                            if self._current_page == 'booking':
                                self._bookings_page.set_search(text)
                            else:
                                if self._current_page == 'warehouse':
                                    self._warehouse_page.apply_search(text)
                                else:
                                    if self._current_page == 'cash_diff':
                                        self._cash_diff_page.apply_search(text)
                                    else:
                                        if self._current_page == 'active':
                                            self._closed_page.set_search(text)
                                        else:
                                            table = self._page_tables.get(self._current_page)
                                            if not table:
                                                return
                                            else:
                                                for row in range(table.rowCount()):
                                                    hay = ' '.join((table.item(row, c).text().lower() if table.item(row, c) else '' for c in range(table.columnCount())))
                                                    table.setRowHidden(row, bool(q and q not in hay))
    def _primary_action_clicked(self) -> None:
        key = self._current_page
        if key == 'bar':
            self._open_market('all', sales_only=False)
        else:
            if key == 'warehouse':
                self._open_market('all', sales_only=False)
            else:
                if key == 'debtors':
                    if hasattr(self, '_debtors_page'):
                        self._debtors_page.add_debtor()
                        self._refresh_current_page()
                else:
                    if key == 'clients':
                        if hasattr(self, '_clients_page'):
                            self._clients_page.add_client()
                            self._refresh_current_page()
                    else:
                        if key == 'booking':
                            self._add_booking_dialog()
                        else:
                            if key == 'expenses':
                                if hasattr(self, '_expenses_page'):
                                    self._expenses_page.add_expense()
                                    self._refresh_current_page()
                                else:
                                    self._add_expense_dialog()
                            else:
                                self._refresh_current_page()
    def _add_booking_dialog(self) -> None:
        from app.ui.dialogs.booking_dialog import BookingDialog
        ids = self._container.stations.list_station_ids()
        dlg = BookingDialog(self, station_ids=ids, station_label=lambda sid: self._container.stations.display_name(sid))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            sid = dlg.station_id() or (ids[0] if ids else '')
            try:
                self._container.finance.add_booking(dlg.client_name(), dlg.client_phone(), str(sid), dlg.booking_time_iso(), dlg.note.text())
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
            self._apply_bookings_to_cards()
            self._update_sidebar_counts()
            self._refresh_current_page()
    def _apply_bookings_to_cards(self) -> None:
        try:
            import database as db
            mapping = db.active_bookings_by_station()
        except Exception:
            mapping = {}
        for sid, card in self._cards.items():
            card.set_booking(mapping.get(sid))
    def _update_sidebar_counts(self) -> None:
        try:
            n_book = len(self._container.finance.bookings(''))
        except Exception:
            n_book = 0
        n_st = len(self._cards)
        if 'stations' in self._nav_buttons:
            icon = self._nav_icons.get('stations', '⚙')
            self._nav_buttons['stations'].setText(f'{icon}  Stollar ({n_st})')
        if 'booking' in self._nav_buttons:
            icon = self._nav_icons.get('booking', '◷')
            self._nav_buttons['booking'].setText(f'{icon}  Bronlaw ({n_book})')
    def _add_expense_dialog(self) -> None:
        from app.ui.dialogs.finance_dialogs import ExpenseAddDialog
        dlg = ExpenseAddDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            etype, amount, wallet, note = dlg.values()
            try:
                self._container.finance.add_expense(etype, amount, wallet, note)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
            self._refresh_current_page()
    def _open_market(self, mode: str='all', sales_only: bool=False, preselect: dict | None=None) -> None:
        try:
            from app.ui.panels.market_panel import MarketPanelDialog
            dlg = MarketPanelDialog(self, mode=mode, sales_only=sales_only, preselect=preselect, with_market=True)
            if not sales_only and hasattr(dlg, 'tabs'):
                    dlg.tabs.setCurrentIndex(1)
            dlg.exec()
            self._refresh_revenue_banner()
            self._refresh_current_page()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
    def _open_admin(self) -> None:
        try:
            from app.ui.panels import admin_panel_new as admin_panel
        except ImportError:
            from app.ui.panels import admin_panel
        try:
            if admin_panel.AdminLoginDialog().exec() == admin_panel.AdminLoginDialog.DialogCode.Accepted:
                dlg = admin_panel.AdminPanelDialog(self)
                if hasattr(dlg, 'station_count_changed'):
                    dlg.station_count_changed.connect(lambda _c: self.refresh_all_cards())
                if hasattr(dlg, 'station_settings_changed'):
                    dlg.station_settings_changed.connect(self.refresh_station_display_names)
                dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
    def _populate_station_grid(self, *, wake_restored_tvs: bool=False) -> None:
        ids = self._container.stations.list_station_ids()
        cols, compact = _grid_layout_for_count(len(ids))
        self._grid.setSpacing(6 if compact else 9)
        for i, sid in enumerate(ids):
            card = StationCard(sid, self._any_card_changed, compact=compact, container=self._container, wake_restored_tvs=wake_restored_tvs)
            card.session_receipt.connect(self._on_session_receipt)
            self._cards[sid] = card
            self._grid.addWidget(card, i // cols, i % cols)
        self._grid.setColumnStretch(0, 1)
        self._update_footer_logo(compact)
        self._apply_bookings_to_cards()
        self._update_sidebar_counts()
    def refresh_all_cards(self) -> None:
        """Kartalarni qayta chizish — ochiq stollarga HDMI/unblock YUBORILMAYDI."""
        for card in self._cards.values():
            card._stop_thread_only()
            card.deleteLater()
        self._cards.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._populate_station_grid(wake_restored_tvs=False)
        self._refresh_customer_display()
        self._refresh_current_page()
    def refresh_station_display_names(self) -> None:
        for card in self._cards.values():
            card.refresh_display_name()
    def transfer_session_time(self, from_id: str, to_id: str) -> None:
        src = self._cards.get(from_id)
        dst = self._cards.get(to_id)
        if not src or not dst:
            return None
        else:
            if not src._can_transfer_time():
                QMessageBox.warning(self, 'Xatolik', 'Bu stolda ko\'chirish mumkin emas.')
                return
            else:
                if dst._busy:
                    QMessageBox.warning(self, 'Band', f'{dst.display_name()} hozir band.')
                    return
                else:
                    is_vip = bool(src._vip_open)
                    payload = src._snapshot_transfer_payload()
                    if not payload:
                        QMessageBox.warning(self, 'Xatolik', 'Ko\'chirib bo\'lmadi.')
                        return
                    else:
                        ok = dst._accept_vip_transfer(payload) if is_vip else dst._accept_timed_transfer(payload)
                        if not ok:
                            src._resume_after_failed_transfer(payload)
                            QMessageBox.warning(self, 'Xatolik', 'VIP ko\'chirib bo\'lmadi.' if is_vip else 'Vaqtni ko\'chirib bo\'lmadi.')
                            return
                        else:
                            src._finalize_transfer_out()
                            self._container.tv.sync_active_sessions()
    def _any_card_changed(self) -> None:
        self._refresh_revenue_banner()
        self._refresh_customer_display()
        if self._current_page in {'balance', 'active'}:
            self._refresh_current_page()
    def _refresh_revenue_banner(self) -> None:
        total = self._presenter.today_revenue()
        self._today_revenue.setText(f'🏆 Daromad: <span style=\'color:{GOLD};\'><b>{total:,.0f}</b></span> so\'m')
    def _refresh_today_revenue_banner(self) -> None:
        """StationCard STOP chaqiruvi bilan moslik."""
        self._refresh_revenue_banner()
    def _on_refresh_revenue_clicked(self) -> None:
        try:
            from app.core import network_time
            network_time.get_network_time().sync(force=True)
        except Exception:
            pass
        self._refresh_revenue_banner()
        self._refresh_customer_display()
        if self._current_page in {'cash', 'click', 'active', 'balance'}:
            self._refresh_current_page()
        try:
            if hasattr(self, '_closed_page') and self._closed_page is not None:
                    self._closed_page.reload()
        except Exception:
            pass
        try:
            if hasattr(self, '_click_page') and self._click_page is not None:
                    self._click_page.reload()
        except Exception:
            pass
        try:
            total = self._presenter.today_revenue()
            self._btn_refresh_revenue.setToolTip(f'Yangilandi: {total:,.0f} so\'m — qayta bosish uchun')
        except Exception:
            return None
    def _show_customer_display(self) -> None:
        try:
            self._customer_display.show_on_customer_screen()
            self._refresh_customer_display()
        except Exception as e:
            logger.warning('Mijoz ekrani: %s', e)
    def _refresh_customer_display(self) -> None:
        try:
            if len(QApplication.screens()) >= 2 and (not self._customer_display.isVisible()):
                    self._customer_display.show_on_customer_screen()
            self._customer_display.update_from_cards(self._cards)
        except Exception as e:
            logger.warning('Mijoz ekrani yangilanmadi: %s', e)
    def _on_session_receipt(self, payload: dict) -> None:
        """Stol yopilganda hisobot + Click/Naqd; preview da monitor + operator 8s."""
        try:
            self._customer_display.show_session_receipt(payload)
        except Exception as e:
            logger.warning('Hisobot mijoz ekranida chiqmadi: %s', e)
        if payload.get('preview'):
            try:
                from app.ui.dialogs.customer_display import show_operator_receipt
                show_operator_receipt(self, payload, int(payload.get('operator_ms') or 8000))
            except Exception as e:
                logger.warning('Operator cheki: %s', e)
        if payload.get('preview') or payload.get('rollover'):
            if payload.get('rollover'):
                try:
                    self._refresh_revenue_banner()
                except Exception:
                    pass
            return None
        else:
            try:
                from PyQt6.QtWidgets import QDialog
                from app.ui.dialogs.station_dialogs import SessionPaymentDialog
                import database as db
                billable = payload.get('billable_total')
                total = float(billable if billable is not None else payload.get('total') or 0)
                dlg = SessionPaymentDialog(total, station=str(payload.get('station') or ''), time_rev=float(payload.get('time_rev') or 0), goods=float(payload.get('drink_total') or 0), parent=self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    click_amt = dlg.click_amount()
                    cash_amt = dlg.cash_amount()
                    if click_amt > 0:
                        try:
                            db.add_click(click_amt)
                        except Exception as e:
                            QMessageBox.warning(self, 'Click', str(e))
                    try:
                        self._customer_display.update_receipt_payment(click_amt, cash_amt)
                    except Exception:
                        pass
                    try:
                        if hasattr(self, '_click_page') and self._click_page is not None:
                                self._click_page.reload()
                    except Exception:
                        pass
            except Exception as e:
                logger.warning('To\'lov dialogi: %s', e)
            self._refresh_revenue_banner()
    def _update_footer_logo(self, compact: bool) -> None:
        logo_path = resource_path('ps_logo.png')
        if not logo_path or not logo_path.exists():
            self._footer_widget.setVisible(False)
            return
        else:
            pix = QPixmap(str(logo_path))
            if pix.isNull():
                self._footer_widget.setVisible(False)
                return
            else:
                self._footer_logo.setPixmap(pix.scaled(120 if compact else 160, 28 if compact else 40, Qt.AspectRatioMode.KeepAspectRatio))
    def _start_timers(self) -> None:
        self._persistent_block_timer = QTimer(self)
        self._persistent_block_timer.setInterval(8000)
        self._persistent_block_timer.timeout.connect(self._check_all_blocking)
        self._persistent_block_timer.start()
        self._vidaa_timer = QTimer(self)
        self._vidaa_timer.setInterval(10000)
        self._vidaa_timer.timeout.connect(self._check_vidaa_blocking)
        self._vidaa_timer.start()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._customer_timer = QTimer(self)
        self._customer_timer.timeout.connect(self._refresh_customer_display)
        self._customer_timer.start(1000)
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._sync_time)
        self._sync_timer.start(120000)
        self._license_timer = QTimer(self)
        self._license_timer.timeout.connect(self._runtime_license_check)
        self._license_timer.start(60000)
        self._update_clock()
        self._sync_time()
        self._update_admin_badge()
    def _update_clock(self) -> None:
        try:
            from app.core import network_time
            text, _ = network_time.get_network_time().format_display()
            self._clock_label.setText(text)
        except Exception:
            return None
    def _sync_time(self) -> None:
        """Tarmoq sinxroni fon oqimida — UI / stol taymeri to\'xtamasin."""
        from PyQt6.QtCore import QThread
        class _SyncThread(QThread):
            def run(self) -> None:
                try:
                    from app.core import network_time
                    network_time.get_network_time().sync(force=True)
                except Exception:
                    return None
        th = _SyncThread(self)
        def _done() -> None:
            self._update_clock()
            self._update_admin_badge()
        th.finished.connect(_done)
        th.start()
        self._net_sync_thread = th
    def _update_admin_badge(self) -> None:
        try:
            st = self._container.license.verify()
            self._btn_admin.set_badge(st.show_expiry_warning)
        except Exception:
            return None
    def _runtime_license_check(self) -> None:
        if self._license_blocked:
            return
        else:
            lic = self._container.license.runtime_check()
            if lic.valid:
                self._update_admin_badge()
                return
            else:
                self._license_blocked = True
                QApplication.clipboard().setText(lic.hwid)
                QMessageBox.critical(self, 'Litsenziya tugadi', lic.message or 'Litsenziya muddati tugagan.')
                QApplication.quit()
    def _check_all_blocking(self) -> None:
        for card in self._cards.values():
            if not card._busy:
                card._re_block_if_free()
    def _check_vidaa_blocking(self) -> None:
        try:
            import vidaa_platform
        except Exception:
            return None
        for card in self._cards.values():
            if card._busy:
                continue
            else:
                try:
                    settings = self._container.stations.tv_settings(card.station_id)
                    if vidaa_platform.is_vidaa_brand(settings.brand) and settings.tv_ip:
                            card._re_block_if_free()
                except Exception:
                    continue
    def restart_zakaz_server(self) -> tuple[bool, str]:
        """QR ЗАКАЗ — lokal server darhol; internet tunnel fonda."""
        from app.services.zakaz_google import stop_zakaz_google
        from app.services.zakaz_server import start_zakaz_server, stop_zakaz_server, zakaz_url
        from app.services.zakaz_settings import get_zakaz_enabled, get_zakaz_port, set_public_base_url
        from app.services.zakaz_telegram import stop_zakaz_telegram
        from app.services.zakaz_tunnel import stop_tunnel
        stop_zakaz_server()
        stop_zakaz_telegram()
        stop_zakaz_google()
        stop_tunnel()
        set_public_base_url('')
        if not get_zakaz_enabled():
            return (True, 'QR ЗАКАЗ o\'chirilgan.')
        else:
            port = get_zakaz_port()
            try:
                start_zakaz_server(port, lambda n: self._zakaz_bridge.called.emit(int(n)))
            except Exception as e:
                return (False, f'Lokal server xato: {e}')
            try:
                self._export_zakaz_qr_files('')
            except Exception:
                pass
            from PyQt6.QtCore import QThread
            class _TunnelThread(QThread):
                def __init__(self, parent, p: int) -> None:
                    super().__init__(parent)
                    self._port = p
                    self.public = ''
                def run(self) -> None:
                    from app.services.zakaz_tunnel import start_tunnel
                    try:
                        self.public = start_tunnel(self._port, wait_sec=55.0) or ''
                    except Exception:
                        self.public = ''
            th = _TunnelThread(self, port)
            def _done() -> None:
                pub = th.public
                if pub:
                    set_public_base_url(pub)
                    try:
                        self._export_zakaz_qr_files(pub)
                    except Exception:
                        pass
                    logger.info('Zakaz public URL: %s', pub)
            th.finished.connect(_done)
            th.start()
            self._zakaz_tunnel_thread = th
            sample = zakaz_url(1, port)
            return (True, f'ЗАКАЗ yoqildi (LAN):\n{sample}\n\nInternet tunnel fonda ochilmoqda — tayyor bo\'lganda ZAKAZ_QR_5.png yangilanadi.')
    def _export_zakaz_qr_files(self, public_base: str) -> None:
        from pathlib import Path
        from app.core.paths import application_dir
        from app.services.zakaz_qr_export import make_qr_sheet_png
        from app.services.zakaz_server import make_qr_png
        from app.services.zakaz_settings import zakaz_page_url
        urls = [zakaz_page_url(n, base=public_base or None) for n in range(1, 6)]
        out = application_dir() / 'ZAKAZ_QR_5.png'
        make_qr_sheet_png(urls, labels=[f'ЗАКАЗ #{n}' for n in range(1, 6)], out_path=out)
        for n, url in enumerate(urls, start=1):
            (application_dir() / f'zakaz_qr_{n}.png').write_bytes(make_qr_png(url, box_size=10))
        dist = application_dir() / 'dist'
        if dist.is_dir():
            import shutil
            shutil.copy2(out, dist / 'ZAKAZ_QR_5.png')
            for n in range(1, 6):
                p = application_dir() / f'zakaz_qr_{n}.png'
                if p.is_file():
                    shutil.copy2(p, dist / p.name)
    def trigger_zakaz(self, n: int) -> None:
        self._on_zakaz(int(n))
    def _on_zakaz(self, n: int) -> None:
        try:
            from app.services.zakaz_audio import play_zakaz_sound
            play_zakaz_sound(int(n))
        except Exception as e:
            logger.warning('Zakaz audio: %s', e)
        if hasattr(self, '_customer_display'):
            try:
                self._customer_display.show_zakaz_number(int(n), 2000)
            except Exception as e:
                logger.warning('Zakaz display: %s', e)
    def closeEvent(self, event) -> None:
        for card in self._cards.values():
            card._stop_thread_only()
        try:
            from app.services.zakaz_google import stop_zakaz_google
            from app.services.zakaz_server import stop_zakaz_server
            from app.services.zakaz_telegram import stop_zakaz_telegram
            from app.services.zakaz_tunnel import stop_tunnel
            stop_zakaz_server()
            stop_zakaz_telegram()
            stop_zakaz_google()
            stop_tunnel()
        except Exception:
            pass
        if hasattr(self, '_customer_display'):
            self._customer_display.close()
        self._container.tv.shutdown()
        super().closeEvent(event)