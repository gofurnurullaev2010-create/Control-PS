"""Legacy asosiy oyna (python main.py). Modular shell: app.ui.main_window."""
from __future__ import annotations
import logging
import re
import sys
from datetime import datetime
from typing import Callable, Dict, Optional
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QAction, QFont, QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
import database as db
from app.tv.tv_handler import TVHandler
from app.ui.dialogs.colors import ACCENT, ACCENT_HOVER, BG_CARD, BG_HEADER, BG_MAIN, BORDER_COLOR, COL_BLUE, COL_GREEN, COL_RED, GOLD_COLOR, STATUS_FREE, TEXT_PRIMARY, TEXT_SECONDARY
from app.ui.dialogs.station_dialogs import TransferTimeDialog, VolumeDialog, VIPStartDialog, OrderTypeDialog, _OrderTypeDialog
from app.ui.dialogs.finance_dialogs import PriceDialog, ReportDialog, DebtorAddDialog, DebtorAdjustDialog, DebtorsDialog, ExpenseAddDialog
from app.ui.dialogs.admin_dialogs import PasswordDialog, AdminDialog, PasswordChangeDialog, OperatorReportDialog
from app.ui.dialogs.tv_settings_dialog import TVSettingsDialog
from app.ui.dialogs.customer_display import CustomerDisplayWindow
from app.ui.widgets.admin_button import AdminButtonWidget, _AdminButtonWidget
from app.ui.widgets.grid_helpers import JOYSTICK_FREE_COUNT, TRANSFER_ICON_FILE, grid_layout_for_count as _grid_layout_for_count, right_cluster_width as _right_cluster_width, station_col_widths as _station_col_widths
from app.ui.widgets.product_card import ProductCard
from app.ui.widgets.station_card import SessionTimer, StationCard
from app.ui.panels.cash_close_page import CashClosePage
from app.ui.panels.balance_page import BalancePage
logger = logging.getLogger(__name__)
BG_IMAGE = 'ps_bg.jpg'
admin_panel = None
market_panel = None
ADMIN_AVAILABLE = True
MARKET_AVAILABLE = True
TEXT_MUTED = '#94A3B8'
BG_CARD_HOVER = '#F8FAFC'
COL_CYAN = '#0284C7'
STATUS_BUSY = '#DC2626'
JOYSTICK_DAILY_LIMIT = 3
JOYSTICK_TEST_SECONDS = 300
STATIONS_GRID_COLS = 1
def _resource_path(filename: str) -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / filename
    else:
        return Path(__file__).resolve().parents[2] / filename
class MainWindow(QMainWindow):
    """Asosiy oyna: kartalar grid, admin tugmalari."""
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Control PS - PlayStation Boshqaruv Tizimi')
        self.setGeometry(0, 0, 1920, 1080)
        logo_path = _resource_path('ps_logo.png')
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
            print(f'MainWindow: logo yuklandi {logo_path}')
        self._build_main_shell()
        self.showMaximized()
        self._persistent_block_timer = QTimer(self)
        self._persistent_block_timer.setInterval(8000)
        self._persistent_block_timer.timeout.connect(self._check_all_stations_blocking)
        self._persistent_block_timer.start()
        self._vidaa_fast_block_timer = QTimer(self)
        self._vidaa_fast_block_timer.setInterval(2000)
        self._vidaa_fast_block_timer.timeout.connect(self._check_vidaa_stations_blocking)
        self._vidaa_fast_block_timer.start()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_network_clock)
        self._clock_timer.start(1000)
        self._customer_display_timer = QTimer(self)
        self._customer_display_timer.timeout.connect(self._refresh_customer_display)
        self._customer_display_timer.start(1000)
        self._network_sync_timer = QTimer(self)
        self._network_sync_timer.timeout.connect(self._sync_network_time)
        self._network_sync_timer.start(120000)
        self._license_check_timer = QTimer(self)
        self._license_check_timer.timeout.connect(self._runtime_license_check)
        self._license_check_timer.start(60000)
        self._license_blocked = False
        self._update_network_clock()
        self._sync_network_time()
        self._update_admin_badge()
    def _build_main_shell(self) -> None:
        """Rasmlardagi Material uslubiga yaqin asosiy shell."""
        self._page_titles = {'stations': 'Stollar', 'active': 'Jabilg\'an', 'bar': 'BAR', 'booking': 'Bronlaw', 'cash': 'Kassa jabıw', 'click': 'CLICK', 'cash_diff': 'Kassa parqi', 'warehouse': 'Sklad', 'debtors': 'Qarizdarlar', 'balance': 'Balans', 'expenses': 'Qa\'rejetler', 'clients': 'Klientler', 'about': 'Haqqında'}
        self._current_page = 'stations'
        self._nav_buttons = {}
        self._page_tables = {}
        self._page_index = {}
        self._bar_cards = []
        self._bar_grid = None
        self._bar_reorder_mode = False
        self._bar_reorder_first = None
        self._bar_products = []
        self._bar_reorder_banner = None
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
        brand_lay.setSpacing(10)
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(38, 38)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = _resource_path('ps_logo.png')
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                logo_lbl.setPixmap(pix.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if logo_lbl.pixmap() is None:
            logo_lbl.setText('E')
            logo_lbl.setStyleSheet('background:#6B7C3B;color:#FFFFFF;border-radius:19px;font-weight:900;')
        title = QLabel('Eagle Playstation')
        title.setStyleSheet('color:#202124;font-size:18px;font-weight:700;')
        brand_lay.addWidget(logo_lbl)
        brand_lay.addWidget(title, 1)
        side_lay.addWidget(brand)
        nav_items = [('stations', '⚙', 'Stollar (0)'), ('active', '◎', 'Jabilg\'an'), ('bar', '☕', 'BAR'), ('booking', '◷', 'Bronlaw (0)'), ('cash', '▦', 'Kassa jabıw'), ('click', '💳', 'CLICK'), ('cash_diff', '⇄', 'Kassa parqi'), ('warehouse', '▣', 'Sklad'), ('debtors', '⌂', 'Qarizdarlar'), ('balance', '$', 'Balans'), ('expenses', '♙', 'Qa\'rejetler'), ('clients', '⚭', 'Klientler')]
        self._nav_icons = {k: ic for k, ic, _t in nav_items}
        self._nav_icons['about'] = 'ⓘ'
        for key, icon, text in nav_items:
            btn = self._make_sidebar_button(icon, text, key)
            self._nav_buttons[key] = btn
            side_lay.addWidget(btn)
        side_lay.addSpacing(8)
        self._btn_admin = _AdminButtonWidget()
        self._btn_admin._btn.setText('⚙  Admin')
        self._btn_admin._btn.setStyleSheet(self._sidebar_button_css(False))
        self._btn_admin._badge.setStyleSheet(f'background-color: {COL_RED}; border-radius: 7px; border: 2px solid #FFFFFF;')
        self._btn_admin.clicked.connect(self._open_admin)
        side_lay.addWidget(self._btn_admin)
        about = self._make_sidebar_button('ⓘ', 'Haqqında', 'about')
        self._nav_buttons['about'] = about
        side_lay.addWidget(about)
        side_lay.addStretch()
        content = QWidget()
        content.setObjectName('Content')
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)
        root.addWidget(content, 1)
        self._today_revenue = QLabel()
        self._today_revenue.setTextFormat(Qt.TextFormat.RichText)
        self._today_revenue.setStyleSheet('color:#202124;font-size:12px;font-weight:800;padding:6px 8px;')
        self._refresh_today_revenue_banner()
        appbar = QWidget()
        appbar.setObjectName('AppBar')
        appbar_lay = QHBoxLayout(appbar)
        appbar_lay.setContentsMargins(14, 8, 14, 8)
        appbar_lay.setSpacing(10)
        self._page_heading = QLabel('Stollar')
        self._page_heading.setStyleSheet('color:#202124;font-size:18px;font-weight:700;')
        appbar_lay.addWidget(self._page_heading)
        appbar_lay.addStretch()
        self._search = QLineEdit()
        self._search.setObjectName('GlobalSearch')
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(430)
        self._search.textChanged.connect(self._on_search_changed)
        appbar_lay.addWidget(self._search)
        self._clock_label = QLabel()
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        appbar_lay.addWidget(self._clock_label)
        self._btn_refresh_revenue = QPushButton('🔄')
        self._btn_refresh_revenue.setToolTip('Daromadni yangilash (yopilgan stollar)')
        self._btn_refresh_revenue.setFixedSize(40, 36)
        self._btn_refresh_revenue.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh_revenue.setStyleSheet('QPushButton{background:#FEF3C7;color:#92400E;border:1px solid #F59E0B;border-radius:10px;font-size:16px;font-weight:900;}QPushButton:hover{background:#FDE68A;}QPushButton:pressed{background:#FBBF24;}')
        self._btn_refresh_revenue.clicked.connect(self._on_refresh_revenue_clicked)
        appbar_lay.addWidget(self._btn_refresh_revenue)
        appbar_lay.addWidget(self._today_revenue)
        content_lay.addWidget(appbar)
        titlebar = QWidget()
        titlebar.setObjectName('TitleBar')
        title_lay = QHBoxLayout(titlebar)
        title_lay.setContentsMargins(14, 10, 14, 8)
        title_lay.setSpacing(8)
        self._content_title = QLabel('Stollar (0)')
        self._content_title.setStyleSheet('color:#202124;font-size:16px;font-weight:700;')
        title_lay.addWidget(self._content_title)
        title_lay.addStretch()
        self._primary_action = QPushButton('+ Qo\'sıw')
        self._primary_action.setObjectName('PrimaryAction')
        self._primary_action.clicked.connect(self._on_primary_action)
        title_lay.addWidget(self._primary_action)
        content_lay.addWidget(titlebar)
        self._stack = QStackedWidget()
        content_lay.addWidget(self._stack, 1)
        self._build_pages()
        self._normal_btns_widget = QWidget()
        self._sales_btns_widget = QWidget()
        self._normal_btns_widget.setVisible(False)
        self._sales_btns_widget.setVisible(False)
        self._sales_mode = False
        self._cards = {}
        self._populate_station_grid(wake_restored_tvs=True)
        self._customer_display = CustomerDisplayWindow()
        self._show_customer_display()
        from PyQt6.QtCore import QObject, pyqtSignal
        class _ZakazBridge(QObject):
            called = pyqtSignal(int)
        self._zakaz_bridge = _ZakazBridge(self)
        self._zakaz_bridge.called.connect(self._on_zakaz)
        self.restart_zakaz_server()
        self._apply_material_style()
        self._set_page('stations')
    def _build_pages(self) -> None:
        stations_page = QWidget()
        stations_lay = QVBoxLayout(stations_page)
        stations_lay.setContentsMargins(0, 0, 0, 0)
        stations_lay.setSpacing(0)
        stations_lay.addWidget(self._build_column_header())
        scroll = QScrollArea()
        scroll.setObjectName('StationsScroll')
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName('StationsViewport')
        self._grid = QGridLayout(inner)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(inner)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        stations_lay.addWidget(scroll, 1)
        self._footer_widget = QWidget()
        footer = QHBoxLayout(self._footer_widget)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setContentsMargins(4, 2, 4, 2)
        self._footer_logo = QLabel()
        footer.addWidget(self._footer_logo)
        stations_lay.addWidget(self._footer_widget)
        self._add_page('stations', stations_page)
        from app.ui.panels.closed_sessions_page import ClosedSessionsPage
        self._closed_page = ClosedSessionsPage(self)
        self._add_page('active', self._closed_page)
        self._add_page('bar', self._build_bar_page())
        from app.ui.panels.bookings_page import BookingsPage
        self._bookings_page = BookingsPage(self, on_changed=lambda: (self._apply_bookings_to_cards(), self._update_sidebar_counts()))
        self._add_page('booking', self._bookings_page)
        self._cash_page = CashClosePage(self, on_cancel=lambda: self._set_page('stations'), on_saved=lambda: (self._refresh_today_revenue_banner(), getattr(self, '_cash_diff_page', None) and self._cash_diff_page.reload()))
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
        self._add_page('about', self._build_empty_page('Eagle Playstation boshqaruv tizimi'))
    def _add_page(self, key: str, page: QWidget) -> None:
        self._page_index[key] = self._stack.addWidget(page)
    def _sidebar_button_css(self, selected: bool) -> str:
        bg = '#F1F4EC' if selected else '#FFFFFF'
        color = '#202124' if selected else '#5F6368'
        weight = '800' if selected else '600'
        return (
            f'QPushButton {{background:{bg}; color:{color}; border:none; border-radius:0;'
            f'text-align:left; padding:10px 16px; font-size:13px;font-weight:{weight}'
            f';}}QPushButton:hover {{ background:#F6F7F3; color:#202124; }}'
        )
    def _make_sidebar_button(self, icon: str, text: str, key: str) -> QPushButton:
        btn = QPushButton(f'{icon}  {text}')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(42)
        btn.setStyleSheet(self._sidebar_button_css(False))
        btn.clicked.connect(lambda _=False, k=key: self._set_page(k))
        return btn
    def _apply_material_style(self) -> None:
        self.setStyleSheet(f'\n            QWidget#MainCentral, QWidget#Content {{ background:#FAFAFA; }}\n            QWidget#Sidebar {{ background:#FFFFFF; border-right:1px solid #E6E6E6; }}\n            QWidget#AppBar {{ background:#FFFFFF; border-bottom:1px solid #E6E6E6; }}\n            QWidget#TitleBar {{ background:#FFFFFF; border-bottom:1px solid #EEEEEE; }}\n            QPushButton#PrimaryAction {{\n                background:#6B7C3B; color:#FFFFFF; border:none; border-radius:3px;\n                padding:8px 14px; font-weight:700;\n            }}\n            QPushButton#IconAction {{\n                background:#FFFFFF; color:#5F6368; border:1px solid #E0E0E0; border-radius:3px;\n                padding:8px 10px; font-weight:700;\n            }}\n            QLineEdit#GlobalSearch {{\n                background:#F1F3F4; color:#202124; border:none; border-radius:3px;\n                padding:9px 14px; font-size:13px;\n            }}\n            QScrollArea#StationsScroll, QScrollArea#BarScroll {{ border:none; background:transparent; }}\n            QWidget#BarPage, QWidget#BarViewport {{ background:#F5F5F5; }}\n            QWidget#StationsViewport {{ background:transparent; }}\n            QScrollBar:vertical {{ background:#F1F3F4; width:10px; margin:2px; }}\n            QScrollBar::handle:vertical {{ background:#C7CCD1; border-radius:5px; min-height:30px; }}\n            QMessageBox {{ background-color:{BG_CARD}; }}\n            QMessageBox QLabel {{ color:{TEXT_PRIMARY}; font-size:14px; }}\n            ')
    def _build_table_page(self, key: str, headers: list[str]) -> QWidget:
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
        table.setAlternatingRowColors(True)
        table.setStyleSheet('\n            QTableWidget { background:#FFFFFF; color:#202124; border:none; gridline-color:#EEEEEE; }\n            QTableWidget::item { padding:7px; border-bottom:1px solid #EEEEEE; }\n            QTableWidget::item:selected { background:#F1F4EC; color:#202124; }\n            QHeaderView::section {\n                background:#FFFFFF; color:#4A4A4A; padding:8px;\n                border:1px solid #EEEEEE; font-weight:800;\n            }\n            ')
        lay.addWidget(table)
        self._page_tables[key] = table
        return page
    def _build_bar_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName('BarPage')
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
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
    def _build_empty_page(self, text: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet('color:#777777;font-size:13px;')
        lay.addWidget(lbl)
        return page
    def _set_page(self, key: str) -> None:
        if key not in self._page_index:
            return
        else:
            self._current_page = key
            self._stack.setCurrentIndex(self._page_index[key])
            title = self._page_titles.get(key, key)
            self._page_heading.setText(title)
            self._content_title.setText(title)
            self._search.setPlaceholderText(f'Izlew {title}')
            for nav_key, btn in self._nav_buttons.items():
                btn.setStyleSheet(self._sidebar_button_css(nav_key == key))
            self._primary_action.setVisible(key not in {'cash_diff', 'about', 'click', 'stations', 'cash', 'balance', 'active'})
            self._refresh_current_page()
    def _refresh_current_page(self) -> None:
        key = getattr(self, '_current_page', 'stations')
        if key == 'stations':
            self._content_title.setText(f'Stollar ({len(self._cards)})')
            self._on_search_changed(self._search.text())
        else:
            if key == 'active':
                self._closed_page.set_search(self._search.text())
                self._closed_page.reload()
                self._content_title.setText('Jabilg\'an')
            else:
                if key in {'bar', 'warehouse'}:
                    if key == 'warehouse' and hasattr(self, '_warehouse_page'):
                        products = []
                        try:
                            for d in db.get_drink_prices():
                                products.append({'name': f"{d.get('drink_name', '')} {float(d.get('volume') or 0):g} L", 'quantity': int(d.get('quantity') or 0), 'purchase': float(d.get('cost_price') or 0), 'price': float(d.get('price') or 0), 'image': d.get('image')})
                            for m in db.get_market_products():
                                name = str(m.get('name') or '')
                                g = float(m.get('grams') or 0)
                                if g > 0 and f'{g:g}' not in name:
                                        name = f'{name} {g:g} gr'
                                products.append({'name': name, 'quantity': int(m.get('quantity') or 0), 'purchase': float(m.get('cost_price') or 0), 'price': float(m.get('price') or 0), 'image': m.get('image')})
                        except Exception:
                            products = []
                        self._warehouse_page.set_products(products)
                        self._warehouse_page.apply_search(self._search.text())
                        self._content_title.setText(f'Sklad ({len(products)})')
                    else:
                        self._reload_products_page(key)
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
                                if key == 'debtors':
                                    self._debtors_page.set_search(self._search.text())
                                    self._debtors_page.reload()
                                    self._content_title.setText('Qarizdarlar')
                                else:
                                    if key == 'booking':
                                        self._bookings_page.set_search(self._search.text())
                                        self._bookings_page.reload()
                                        self._content_title.setText(f'Bronlaw ({len(db.list_bookings(self._search.text()))})')
                                    else:
                                        if key == 'expenses':
                                            if hasattr(self, '_expenses_page'):
                                                self._expenses_page.set_search(self._search.text())
                                                self._expenses_page.reload()
                                                self._content_title.setText(f'Qa\'rejetler ({self._expenses_page.row_count()})')
                                            else:
                                                self._reload_expenses_page()
                                        else:
                                            if key == 'clients':
                                                self._clients_page.set_search(self._search.text())
                                                self._clients_page.reload()
                                                self._content_title.setText(f'Klientler ({self._clients_page.table.rowCount()})')
                                            else:
                                                if key == 'balance':
                                                    self._reload_balance_page()
        if key == 'stations':
            self._apply_bookings_to_cards()
        self._update_sidebar_counts()
    def _table_set_rows(self, key: str, rows: list[list[object]]) -> None:
        table = self._page_tables.get(key)
        if table is None:
            return
        else:
            table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    if isinstance(value, (int, float)) and col_idx > 0:
                            item.setText(f'{float(value):,.0f}')
                            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(row_idx, col_idx, item)
            table.resizeRowsToContents()
            self._on_search_changed(self._search.text())
    def _reload_active_page(self) -> None:
        rows = []
        for card in self._cards.values():
            if card._busy or card._tv_viewing:
                rows.append(['-', card.display_name(), 'Ko\'rilmekte' if card._busy else 'TV', card._col_played.text(), card._col_total.text()])
        self._table_set_rows('active', rows)
        self._content_title.setText(f'Jablig\'an ({len(rows)})')
    def _reload_products_page(self, key: str) -> None:
        if key == 'bar':
            self._reload_bar_grid()
            return
        else:
            rows = []
            try:
                for item in db.get_drink_prices():
                    name = f"{item.get('drink_name', '')} {float(item.get('volume') or 0):g} L"
                    if key == 'warehouse':
                        rows.append(['', name, int(item.get('quantity') or 0), 0, float(item.get('price') or 0)])
                    else:
                        rows.append([name, 'Suwlar', int(item.get('quantity') or 0), 0, float(item.get('price') or 0)])
                for item in db.get_market_products():
                    name = str(item.get('name') or '')
                    cat = str(item.get('category') or 'Suzarik')
                    if key == 'warehouse':
                        rows.append(['', name, int(item.get('quantity') or 0), 0, float(item.get('price') or 0)])
                    else:
                        rows.append([name, cat, int(item.get('quantity') or 0), 0, float(item.get('price') or 0)])
            except Exception as e:
                logger.warning('Mahsulot sahifasi yangilanmadi: %s', e)
            self._table_set_rows(key, rows)
            self._content_title.setText(f'{self._page_titles[key]} ({len(rows)})')
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
            products_meta = []
            try:
                for item in db.get_drink_prices():
                    name = f"{item.get('drink_name', '')} {float(item.get('volume') or 0):g} L"
                    meta = {'kind': 'drink', 'drink_name': str(item.get('drink_name') or ''), 'volume': float(item.get('volume') or 0), 'name': name, 'image': item.get('image'), 'price': float(item.get('price') or 0), 'purchase': float(item.get('cost_price') or 0), 'quantity': int(item.get('quantity') or 0)}
                    products_meta.append(meta)
                for item in db.get_market_products():
                    name = str(item.get('name') or '').strip()
                    try:
                        g = float(item.get('grams') or 0)
                    except (TypeError, ValueError):
                        g = 0.0
                    if g > 0 and f'{g:g}' not in name:
                            name = f'{name} {g:g} gr'.strip()
                    meta = {'kind': 'market', 'id': int(item.get('id') or 0), 'name': name, 'image': item.get('image'), 'price': float(item.get('price') or 0), 'purchase': float(item.get('cost_price') or 0), 'quantity': int(item.get('quantity') or 0)}
                    products_meta.append(meta)
                products_meta = db.sort_products_by_bar_order(products_meta)
            except Exception as e:
                logger.warning('BAR katalog yangilanmadi: %s', e)
            self._bar_products = list(products_meta)
            cols = 7
            for i, meta in enumerate(products_meta):
                card = ProductCard(str(meta.get('name') or ''), meta.get('image'), price=float(meta.get('price') or 0), purchase=float(meta.get('purchase') or 0), quantity=int(meta.get('quantity') or 0))
                card.clicked.connect(lambda _=False, m=meta: self._on_bar_card_clicked(m))
                card.set_image_requested.connect(lambda m=meta: self._set_bar_product_image(m))
                card.reorder_requested.connect(self._toggle_bar_reorder_mode)
                card.set_reorder_mode(self._bar_reorder_mode, selected=bool(self._bar_reorder_first and db.bar_product_key(self._bar_reorder_first) == db.bar_product_key(meta)))
                self._bar_cards.append(card)
                self._bar_grid.addWidget(card, i // cols, i % cols)
            self._content_title.setText(f'BAR ({len(products_meta)})')
            self._update_bar_reorder_banner()
            self._on_search_changed(self._search.text())
    def _toggle_bar_reorder_mode(self) -> None:
        self._bar_reorder_mode = not self._bar_reorder_mode
        self._bar_reorder_first = None
        self._update_bar_reorder_banner()
        for card in self._bar_cards:
            card.set_reorder_mode(self._bar_reorder_mode, selected=False)
        if self._bar_reorder_mode:
            QMessageBox.information(self, 'Joyini o\'zgartirish', 'BAR tartibini o\'zgartirish yoqildi.\n1) Birinchi tovarni bosing\n2) Ikkinchi tovarni bosing — joylari almashtiriladi.\n\nYana o\'ng tugmani ikki marta bosib rejimni o\'chirasiz.')
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
                    self._bar_reorder_banner.setText(f'Joyini o\'zgartirish: «{name}» tanlandi — endi ikkinchi tovarni bosing. (O\'ng tugma ×2 = yopish)')
                else:
                    self._bar_reorder_banner.setText('Joyini o\'zgartirish rejimi: avval birinchi, so\'ng ikkinchi tovarni bosing. (O\'ng tugma ×2 = yopish)')
                self._bar_reorder_banner.setVisible(True)
    def _on_bar_card_clicked(self, product: dict) -> None:
        if self._bar_reorder_mode:
            if self._bar_reorder_first is None:
                self._bar_reorder_first = dict(product)
                self._update_bar_reorder_banner()
                key = db.bar_product_key(product)
                for i, card in enumerate(self._bar_cards):
                    prod = self._bar_products[i] if i < len(self._bar_products) else {}
                    card.set_reorder_mode(True, selected=db.bar_product_key(prod) == key)
            else:
                first = self._bar_reorder_first
                self._bar_reorder_first = None
                if db.bar_product_key(first) == db.bar_product_key(product):
                    self._update_bar_reorder_banner()
                    for card in self._bar_cards:
                        card.set_reorder_mode(True, selected=False)
                else:
                    try:
                        keys = [db.bar_product_key(p) for p in self._bar_products]
                        db.swap_bar_product_order(db.bar_product_key(first), db.bar_product_key(product), keys)
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
                kind = str(product.get('kind') or '')
                if kind == 'drink':
                    db.set_drink_image(str(product.get('drink_name') or ''), float(product.get('volume') or 0), data)
                else:
                    if kind == 'market':
                        db.update_market_product(int(product.get('id') or 0), image=data, update_image=True)
                    else:
                        raise ValueError('Noma\'lum mahsulot')
                self._reload_bar_grid()
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Rasm saqlanmadi:\n{e}')
    def _reload_income_page(self) -> None:
        rows = []
        for r in db.get_detailed_daily_report():
            s_time = str(r.get('start_time') or '').split('T')[(-1)][:5]
            e_time = str(r.get('end_time') or '').split('T')[(-1)][:5]
            rows.append([r.get('station_id', ''), f'{s_time} - {e_time}', f"{r.get('duration_minutes', 0)} min", r.get('drinks') or '-', float(r.get('revenue') or 0)])
        self._table_set_rows('income', rows)
        self._content_title.setText(f'Kirimler ({len(rows)})')
    def _reload_debtors_page(self) -> None:
        rows = []
        for r in db.list_debtors(self._search.text()):
            name = str(r.get('client_name', ''))
            phone = str(r.get('phone') or '')
            if phone:
                name = f'{name} - {phone}'
            rows.append([name, float(r.get('amount') or 0), self._format_dt_for_table(str(r.get('debt_time') or '')), r.get('note') or ''])
        self._table_set_rows('debtors', rows)
        self._content_title.setText(f'Qarizdarlar ({len(rows)})')
    def _reload_booking_page(self) -> None:
        rows = []
        if hasattr(db, 'list_bookings'):
            for r in db.list_bookings(self._search.text()):
                rows.append([str(r.get('client_name') or ''), str(r.get('station_id') or ''), self._format_dt_for_table(str(r.get('booking_time') or '')), str(r.get('phone') or ''), str(r.get('note') or '')])
        self._table_set_rows('booking', rows)
        self._content_title.setText(f'Bronlaw ({len(rows)})')
    def _reload_expenses_page(self) -> None:
        rows = []
        if hasattr(db, 'list_expenses'):
            for r in db.list_expenses(self._search.text()):
                rows.append([str(r.get('expense_type') or ''), float(r.get('amount') or 0), 'Ceyf puli' if str(r.get('wallet') or '') == 'safe' else 'Kassa puli', str(r.get('note') or ''), self._format_dt_for_table(str(r.get('created_time') or ''))])
        self._table_set_rows('expenses', rows)
        self._content_title.setText(f'Qa\'rejetler ({len(rows)})')
    def _reload_clients_page(self) -> None:
        clients = {}
        for r in db.list_debtors('', include_paid=True):
            key = (str(r.get('client_name') or ''), str(r.get('phone') or ''))
            item = clients.setdefault(key, {'name': key[0], 'phone': key[1], 'debt': 0.0, 'time': str(r.get('debt_time') or '')})
            if not r.get('paid'):
                item['debt'] = float(item.get('debt') or 0) + float(r.get('amount') or 0)
        rows = [[i + 1, c['name'], c['phone'], float(c['debt'] or 0), self._format_dt_for_table(str(c['time'] or ''))] for i, c in enumerate(clients.values())]
        self._table_set_rows('clients', rows)
        self._content_title.setText(f'Klientler ({len(rows)})')
    def _reload_balance_page(self) -> None:
        try:
            report = db.operator_report_for_day()
            cash = float(report.get('expected_amount') or 0)
            safe = float(db.get_safe_balance())
            total = safe + cash
        except Exception as e:
            logger.warning('Balans yangilanmadi: %s', e)
            total = safe = cash = 0.0
        self._balance_page_widget.set_values(total, safe, cash)
    def _on_search_changed(self, text: str) -> None:
        q = (text or '').strip().lower()
        if getattr(self, '_current_page', '') == 'stations':
            for card in self._cards.values():
                card.setVisible(not q or q in card.display_name().lower() or q in card.station_id.lower())
        else:
            if getattr(self, '_current_page', '') == 'bar':
                for card in self._bar_cards:
                    card.setVisible(not q or q in card.display_name().lower())
            else:
                if getattr(self, '_current_page', '') == 'debtors' and hasattr(self, '_debtors_page'):
                    self._debtors_page.set_search(text)
                else:
                    if getattr(self, '_current_page', '') == 'expenses' and hasattr(self, '_expenses_page'):
                        self._expenses_page.set_search(text)
                    else:
                        if getattr(self, '_current_page', '') == 'clients' and hasattr(self, '_clients_page'):
                            self._clients_page.set_search(text)
                        else:
                            if getattr(self, '_current_page', '') == 'booking' and hasattr(self, '_bookings_page'):
                                self._bookings_page.set_search(text)
                            else:
                                if getattr(self, '_current_page', '') == 'warehouse' and hasattr(self, '_warehouse_page'):
                                    self._warehouse_page.apply_search(text)
                                else:
                                    if getattr(self, '_current_page', '') == 'cash_diff' and hasattr(self, '_cash_diff_page'):
                                        self._cash_diff_page.apply_search(text)
                                    else:
                                        if getattr(self, '_current_page', '') == 'active' and hasattr(self, '_closed_page'):
                                            self._closed_page.set_search(text)
                                            return
                                        else:
                                            table = self._page_tables.get(getattr(self, '_current_page', ''))
                                            if table is None:
                                                return
                                            else:
                                                for row in range(table.rowCount()):
                                                    haystack = ' '.join((table.item(row, col).text().lower() for col in range(table.columnCount()) if table.item(row, col)))
                                                    table.setRowHidden(row, bool(q and q not in haystack))
    def _on_primary_action(self) -> None:
        key = getattr(self, '_current_page', 'stations')
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
                            self._add_booking_from_ui()
                        else:
                            if key == 'expenses':
                                if hasattr(self, '_expenses_page'):
                                    self._expenses_page.add_expense()
                                    self._refresh_current_page()
                                else:
                                    self._add_expense_from_ui()
                            else:
                                self._refresh_current_page()
    def _add_booking_from_ui(self) -> None:
        from app.ui.dialogs.booking_dialog import BookingDialog
        station_ids = db.list_station_ids()
        dlg = BookingDialog(self, station_ids=station_ids, station_label=lambda sid: db.get_station_display_name(sid))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            try:
                db.add_booking(dlg.client_name(), dlg.client_phone(), dlg.station_id() or (station_ids[0] if station_ids else ''), dlg.booking_time_iso(), dlg.note.text())
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
            self._apply_bookings_to_cards()
            self._update_sidebar_counts()
            self._refresh_current_page()
    def _add_expense_from_ui(self) -> None:
        dlg = ExpenseAddDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            etype, amount, wallet, note = dlg.values()
            try:
                db.add_expense(etype, amount, wallet, note)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
            self._refresh_current_page()
    @staticmethod
    def _format_dt_for_table(value: str) -> str:
        if 'T' in value:
            d, t = value.split('T', 1)
            return f'{d} г. {t[:8]}'
        else:
            return value
    @staticmethod
    def _top_button_css(accent: str) -> str:
        return f'QPushButton {{  background: rgba(255,255,255,0.05);  color: {TEXT_PRIMARY};  border: 1px solid {BORDER_COLOR};  border-radius: 10px;  padding: 7px 8px;  font-weight: 800;  font-size: 11px;}}QPushButton:hover {{  background: rgba(255,255,255,0.12);  border: 1px solid {accent};}}'
    def _make_top_button(self, icon: str, label: str, accent: str) -> QPushButton:
        btn = QPushButton(f'{icon} {label}')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._top_button_css(accent))
        return btn
    @staticmethod
    def _clock_css() -> str:
        return f'color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 900; padding: 7px 10px; background-color: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid {BORDER_COLOR};'
    def _build_section_header(self) -> QWidget:
        ids = db.list_station_ids()
        prices = {}
        for sid in ids:
            try:
                p = float(db.get_station_price(sid))
            except Exception:
                continue
            prices[p] = prices.get(p, 0) + 1
        price = max(prices, key=prices.get) if prices else 0
        self._brand_sub.setText(f'jami {len(ids)} stansiya')
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(22, 8, 14, 0)
        lay.setSpacing(10)
        bar = QLabel()
        bar.setFixedSize(4, 18)
        bar.setStyleSheet(f'background: {COL_BLUE}; border-radius: 2px;')
        lay.addWidget(bar)
        txt = QLabel(f'STOL · {len(ids)} JOY · {price:,.0f} SO\'M/SOAT')
        txt.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 800; letter-spacing: 1px;')
        lay.addWidget(txt)
        lay.addStretch()
        return w
    def _build_column_header(self) -> QWidget:
        _cols, compact = _grid_layout_for_count(len(db.list_station_ids()))
        cw = _station_col_widths(compact)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(22, 6, 20, 4)
        lay.setSpacing(0)
        def _h(text: str, width: int=0, *, expand: bool=False) -> QLabel:
            lbl = QLabel(text)
            if expand:
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            else:
                lbl.setFixedWidth(width)
            lbl.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 800; letter-spacing: 1px;')
            return lbl
        lay.addWidget(_h('STOL', cw['stol']))
        lay.addWidget(_h('HOLAT', cw['holat']))
        for title in ['BOSHLANGAN', 'O\'YNAGAN', 'PLAYSTATION', 'TOVARLAR', 'UMUMIY']:
            lay.addWidget(_h(title, expand=True), 1)
        spacer = QWidget()
        spacer.setFixedWidth(_right_cluster_width(compact))
        lay.addWidget(spacer)
        return w
    def _update_admin_badge(self) -> None:
        try:
            from app.auth import license_manager
            st = license_manager.get_license_status()
            self._btn_admin.set_badge(st.show_expiry_warning)
        except Exception as e:
            logger.warning('Admin eslatma yangilanmadi: %s', e)
    def _update_network_clock(self) -> None:
        try:
            from app.core import network_time
            text, _color = network_time.get_network_time().format_display()
            self._clock_label.setText(text)
            self._clock_label.setStyleSheet(self._clock_css())
        except Exception as e:
            logger.warning('Soat yangilanmadi: %s', e)
    def _sync_network_time(self) -> None:
        """Tarmoq sinxroni fonda — stol soatlari kechikmasin."""
        from PyQt6.QtCore import QThread
        class _SyncThread(QThread):
            def run(self) -> None:
                try:
                    from app.core import network_time
                    network_time.get_network_time().sync(force=True)
                except Exception as e:
                    logger.warning('Tarmoq vaqti sinxroni: %s', e)
        th = _SyncThread(self)
        def _done() -> None:
            self._update_network_clock()
            self._update_admin_badge()
        th.finished.connect(_done)
        th.start()
        self._net_sync_thread = th
    def _runtime_license_check(self) -> None:
        if self._license_blocked:
            return
        else:
            try:
                from app.auth import license_manager
                lic = license_manager.verify_license_full()
                if lic.valid:
                    self._update_admin_badge()
                    return
                else:
                    self._license_blocked = True
                    QApplication.clipboard().setText(lic.hwid)
                    detail = lic.message or 'Litsenziya muddati tugagan.'
                    QMessageBox.critical(self, 'Litsenziya tugadi', f'{detail}\n\nKompyuter kodi (HWID): {lic.hwid}\n\n(HWID nusxalandi. Dasturchiga yuborib yangi license.key oling.)')
                    QApplication.quit()
            except Exception as e:
                logger.error('Litsenziya tekshiruvi: %s', e)
    def _check_all_stations_blocking(self):
        """Hamma bo\'sh stollarni bloklash holatini yangilab chiqish."""
        for card in self._cards.values():
            if not card._busy:
                card._re_block_if_free()
    def _check_vidaa_stations_blocking(self):
        """VIDAA TV pult bilan yoqib yuborilsa, bo\'sh stolda tez o\'chirish."""
        try:
            import vidaa_platform
        except Exception:
            return None
        for card in self._cards.values():
            if card._busy:
                continue
            else:
                try:
                    settings = db.get_tv_settings(card.station_id)
                    if not vidaa_platform.is_vidaa_brand(settings.brand) or not settings.tv_ip:
                        continue
                    else:
                        card._re_block_if_free()
                except Exception as e:
                    logging.getLogger('tv').warning('VIDAA fast block %s: %s', card.station_id, e)
    def _refresh_today_revenue_banner(self) -> None:
        total = float(db.today_revenue_total())
        self._today_revenue.setText(f'🏆 Daromad: <span style=\'color:{GOLD_COLOR};\'><b>{total:,.0f}</b></span> so\'m')
    def _any_card_changed(self) -> None:
        self._refresh_today_revenue_banner()
        self._refresh_customer_display()
        if getattr(self, '_current_page', '') in {'balance', 'active'}:
            self._refresh_current_page()
    def _show_customer_display(self) -> None:
        try:
            self._customer_display.show_on_customer_screen()
            self._refresh_customer_display()
        except Exception as e:
            logger.warning('Mijoz ekrani ochilmadi: %s', e)
    def _refresh_customer_display(self) -> None:
        try:
            if hasattr(self, '_customer_display'):
                if len(QApplication.screens()) >= 2 and (not self._customer_display.isVisible()):
                    self._customer_display.show_on_customer_screen()
                self._customer_display.update_from_cards(self._cards)
        except Exception as e:
            logger.warning('Mijoz ekrani yangilanmadi: %s', e)
    def _on_refresh_revenue_clicked(self) -> None:
        try:
            from app.core import network_time
            network_time.get_network_time().sync(force=True)
        except Exception:
            pass
        self._refresh_today_revenue_banner()
        self._refresh_customer_display()
        try:
            if hasattr(self, '_click_page') and self._click_page is not None:
                    self._click_page.reload()
        except Exception:
            pass
        try:
            if hasattr(self, '_closed_page') and self._closed_page is not None:
                    self._closed_page.reload()
        except Exception:
            pass
        try:
            total = float(db.today_revenue_total())
            self._btn_refresh_revenue.setToolTip(f'Yangilandi: {total:,.0f} so\'m — qayta bosish uchun')
        except Exception:
            return None
    def _on_session_receipt(self, payload: dict) -> None:
        try:
            if hasattr(self, '_customer_display'):
                self._customer_display.show_session_receipt(payload)
        except Exception as e:
            logger.warning('Hisobot mijoz ekranida chiqmadi: %s', e)
        if payload.get('preview'):
            try:
                from app.ui.dialogs.customer_display import show_operator_receipt
                show_operator_receipt(self, payload, int(payload.get('operator_ms') or 8000))
            except Exception as e:
                logger.warning('Operator cheki: %s', e)
            return
        if payload.get('rollover'):
            self._refresh_today_revenue_banner()
            return
        try:
            from PyQt6.QtWidgets import QDialog
            from app.ui.dialogs.station_dialogs import SessionPaymentDialog
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
                    if hasattr(self, '_customer_display'):
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
        self._refresh_today_revenue_banner()
    def _toggle_sales_mode(self) -> None:
        """PS logosi bosilganda: sotuv rejimini yoqish/o\'chirish.\n\n        Sotuv rejimida yuqori menyuda faqat ICHIMLIK va MARKET sotish tugmalari qoladi\n        (o\'ynamayotgan mijoz ham narsa sotib olishi mumkin). Qayta bosilsa normal holatga qaytadi.\n        """
        self._sales_mode = not getattr(self, '_sales_mode', False)
        self._normal_btns_widget.setVisible(not self._sales_mode)
        self._sales_btns_widget.setVisible(self._sales_mode)
    def _open_market(self, mode: str='all', sales_only: bool=False, preselect: dict | None=None) -> None:
        global market_panel
        global MARKET_AVAILABLE
        if market_panel is None:
            try:
                from app.ui.panels import market_panel as _market_panel
                market_panel = _market_panel
                MARKET_AVAILABLE = True
            except Exception as e:
                MARKET_AVAILABLE = False
                print(f'Market panel import xatoligi: {e}')
        if not MARKET_AVAILABLE:
            QMessageBox.critical(self, 'Xatolik', 'Boshqaruv paneli moduli mavjud emas!\n\nIltimos, market_panel.py faylini tekshiring.')
            return
        else:
            try:
                dlg = market_panel.MarketPanelDialog(self, mode=mode, sales_only=sales_only, preselect=preselect, with_market=True)
                if not sales_only and hasattr(dlg, 'tabs'):
                        dlg.tabs.setCurrentIndex(1)
                dlg.exec()
                self._refresh_today_revenue_banner()
                self._refresh_current_page()
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, 'Xatolik', f'Boshqaruv panelini ochishda xatolik: {str(e)}')
    def _open_report(self) -> None:
        dlg = ReportDialog(self)
        dlg.exec()
    def _open_debtors(self) -> None:
        dlg = DebtorsDialog(self)
        dlg.exec()
        self._refresh_current_page()
    def _open_admin(self) -> None:
        """Admin panelini ochish"""
        global admin_panel
        global ADMIN_AVAILABLE
        if admin_panel is None:
            try:
                from app.ui.panels import admin_panel_new as _admin_panel
            except ImportError:
                from app.ui.panels import admin_panel as _admin_panel
            admin_panel = _admin_panel
            ADMIN_AVAILABLE = True
        dlg = admin_panel.AdminLoginDialog()
        try:
            if dlg.exec() == admin_panel.AdminLoginDialog.DialogCode.Accepted:
                admin_dlg = admin_panel.AdminPanelDialog(self)
                if hasattr(admin_dlg, 'station_count_changed'):
                    admin_dlg.station_count_changed.connect(lambda _count: self.refresh_all_cards())
                if hasattr(admin_dlg, 'station_settings_changed'):
                    admin_dlg.station_settings_changed.connect(self.refresh_station_display_names)
                admin_dlg.exec()
        except Exception as e:
            print(f'Admin panel ochishda xatolik: {e}')
            QMessageBox.critical(self, 'Xatolik', f'Admin panel ochishda xatolik: {str(e)}')
    def _open_tv(self) -> None:
        paused = []
        for name in ['_persistent_block_timer', '_vidaa_timer']:
            t = getattr(self, name, None)
            if t is not None and getattr(t, 'isActive', lambda: False)():
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
    def _open_parol(self) -> None:
        """Kirish parolini o\'zgartirish oynasi"""
        dlg = PasswordChangeDialog(self)
        dlg.exec()
    def _open_operator_report(self) -> None:
        """Operator (smena) hisoboti — parol bilan ko\'rish va Adminga saqlash."""
        dlg = OperatorReportDialog(self)
        dlg.exec()
    def _update_footer_logo(self, compact: bool) -> None:
        logo_path = _resource_path('ps_logo.png')
        if not logo_path.exists():
            self._footer_widget.setVisible(False)
            return
        else:
            pixmap = QPixmap(str(logo_path))
            if pixmap.isNull():
                self._footer_widget.setVisible(False)
                return
            else:
                h = 28 if compact else 40
                w = 120 if compact else 160
                self._footer_logo.setPixmap(pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self._footer_widget.setVisible(True)
    def _populate_station_grid(self, *, wake_restored_tvs: bool=False) -> None:
        """Stol kartalarini gorizontal qatorlarga joylash (bir ustun)."""
        ids = db.list_station_ids()
        cols, compact = _grid_layout_for_count(len(ids))
        self._grid.setSpacing(6 if compact else 9)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._update_footer_logo(compact)
        for i, sid in enumerate(ids):
            card = StationCard(sid, self._any_card_changed, compact=compact, wake_restored_tvs=wake_restored_tvs)
            card.session_receipt.connect(self._on_session_receipt)
            self._cards[sid] = card
            self._grid.addWidget(card, i // cols, i % cols)
        self._grid.setColumnStretch(0, 1)
        self._apply_bookings_to_cards()
        self._update_sidebar_counts()
    def _apply_bookings_to_cards(self) -> None:
        try:
            mapping = db.active_bookings_by_station()
        except Exception:
            mapping = {}
        for sid, card in self._cards.items():
            card.set_booking(mapping.get(sid))
    def _update_sidebar_counts(self) -> None:
        try:
            n_book = len(db.list_bookings(''))
        except Exception:
            n_book = 0
        n_st = len(self._cards)
        if 'stations' in self._nav_buttons:
            ic = self._nav_icons.get('stations', '⚙')
            self._nav_buttons['stations'].setText(f'{ic}  Stollar ({n_st})')
        if 'booking' in self._nav_buttons:
            ic = self._nav_icons.get('booking', '◷')
            self._nav_buttons['booking'].setText(f'{ic}  Bronlaw ({n_book})')
    def refresh_station_display_names(self) -> None:
        """Admin paneldan stol nomlari o\'zgarganda kartochka sarlavhalarini yangilash."""
        for card in self._cards.values():
            card.refresh_display_name()
    def transfer_session_time(self, from_id: str, to_id: str) -> None:
        """Qolgan vaqt yoki VIP seansni band stoldan bo\'sh stolga ko\'chirish."""
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
                    QMessageBox.warning(self, 'Band', f'{dst.display_name()} hozir band. Boshqa bo\'sh stolni tanlang.')
                    return
                else:
                    from_label = src.display_name()
                    to_label = dst.display_name()
                    is_vip = bool(src._vip_open)
                    if is_vip:
                        time_text = StationCard._format_seconds(src._elapsed)
                    else:
                        time_text = StationCard._format_seconds(src._remaining_seconds())
                    payload = src._snapshot_transfer_payload()
                    if not payload:
                        QMessageBox.warning(self, 'Xatolik', 'Ko\'chirib bo\'lmadi.')
                        return
                    else:
                        ok = dst._accept_vip_transfer(payload) if is_vip else dst._accept_timed_transfer(payload)
                        if not ok:
                            src._resume_after_failed_transfer(payload)
                            QMessageBox.warning(self, 'Xatolik', 'VIP seansni ko\'chirib bo\'lmadi. Qayta urinib ko\'ring.' if is_vip else 'Vaqtni ko\'chirib bo\'lmadi. Qayta urinib ko\'ring.')
                        else:
                            src._finalize_transfer_out()
                            try:
                                import tv_handler
                                tv_handler.sync_active_tv_sessions_from_db()
                            except Exception:
                                pass
                            if is_vip:
                                QMessageBox.information(self, 'VIP ko\'chirildi', f'<b>{from_label}</b> bloklandi.<br><b>{to_label}</b> VIP — <b>{time_text}</b> dan davom etmoqda.')
                            else:
                                QMessageBox.information(self, 'Vaqt ko\'chirildi', f'<b>{from_label}</b> bloklandi.<br><b>{to_label}</b> ochildi — qolgan vaqt: <b>{time_text}</b>')
    def refresh_all_cards(self) -> None:
        """Barcha stollarni yangilash (stollar soni o\'zgarganda)"""
        for card in self._cards.values():
            card._stop_thread_only()
            card.deleteLater()
        self._cards.clear()
        while self._grid.count():
            child = self._grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._populate_station_grid(wake_restored_tvs=False)
        self._refresh_customer_display()
        self._refresh_current_page()
    def closeEvent(self, event) -> None:
        if hasattr(self, '_persistent_block_timer'):
            self._persistent_block_timer.stop()
        if hasattr(self, '_customer_display_timer'):
            self._customer_display_timer.stop()
        for c in self._cards.values():
            c._stop_thread_only()
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
        try:
            import tv_handler
            tv_handler.set_main_app_lock_gate(False)
        except Exception:
            pass
        super().closeEvent(event)
    def restart_zakaz_server(self) -> tuple[bool, str]:
        from app.services.zakaz_google import stop_zakaz_google
        from app.services.zakaz_server import start_zakaz_server, stop_zakaz_server, zakaz_url
        from app.services.zakaz_settings import get_zakaz_enabled, get_zakaz_port, set_public_base_url, zakaz_page_url
        from app.services.zakaz_telegram import stop_zakaz_telegram
        from app.services.zakaz_tunnel import start_tunnel, stop_tunnel
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
            public = ''
            try:
                public = start_tunnel(port, wait_sec=30.0) or ''
            except Exception as e:
                logger.warning('Tunnel: %s', e)
            if public:
                set_public_base_url(public)
                return (True, f'Internet ЗАКАЗ:\n{zakaz_page_url(1, base=public)}')
            else:
                return (True, f'Lokal ЗАКАЗ:\n{zakaz_url(1, port)}')
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