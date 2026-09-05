"""Stol kartasi va seans taymeri — ui_manager dan ajratilgan."""
from __future__ import annotations
import logging
import re
import sys
from datetime import datetime
from typing import Callable, Dict, Optional
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QFont, QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from app.tv.tv_handler import TVHandler
from app.services.station_card_port import make_station_card_port
from app.core.network_time import trusted_now_naive
from app.core.ps_billing import billable_seconds as _ps_billable_seconds, parse_session_dt, playstation_amount, wall_seconds as _ps_wall_seconds
from app.ui.dialogs.station_dialogs import BuyurtmaDialog, TransferTimeDialog, VIPStartDialog, VolumeDialog
from app.ui.widgets.grid_helpers import JOYSTICK_FREE_COUNT, TRANSFER_ICON_FILE, right_cluster_width, station_col_widths
logger = logging.getLogger(__name__)
BG_MAIN = '#FFFFFF'
BG_HEADER = '#F6F8FB'
BG_CARD = '#FFFFFF'
BG_CARD_HOVER = '#F8FAFC'
TEXT_PRIMARY = '#111827'
TEXT_SECONDARY = '#64748B'
TEXT_MUTED = '#94A3B8'
ACCENT = '#0EA5E9'
BORDER_COLOR = '#E5E7EB'
COL_CYAN = '#0284C7'
COL_BLUE = '#2563EB'
COL_RED = '#DC2626'
COL_GREEN = '#16A34A'
STATUS_FREE = '#16A34A'
STATUS_BUSY = '#DC2626'
STATUS_BOOKED = '#EAB308'
GOLD_COLOR = '#D97706'
JOYSTICK_DAILY_LIMIT = 3
JOYSTICK_TEST_SECONDS = 300
def _resource_path(filename: str) -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / filename
    else:
        return Path(__file__).resolve().parents[2] / filename
def format_seconds(seconds: int) -> str:
    return StationCard._format_seconds(seconds)
class SessionTimer(QThread):
    """Har bir seans uchun alohida oqim: real (monotonic) vaqt — sleep kechikishi yo\'q."""
    tick = pyqtSignal(int)
    session_ended = pyqtSignal()
    def __init__(self, total_seconds: int, parent: Optional[QWidget]=None, indefinite: bool=False, initial_elapsed: int=0) -> None:
        super().__init__(parent)
        self._indefinite = indefinite
        self._total = max(1, int(total_seconds))
        self._initial_elapsed = max(0, int(initial_elapsed))
        self._running = True
        from threading import Lock
        self._lock = Lock()
    def add_time(self, seconds: int) -> None:
        """Mavjud seansga vaqt qo\'shish."""
        with self._lock:
            self._total += int(seconds)
    def run(self) -> None:
        import time as _time
        start_mono = _time.monotonic() - float(self._initial_elapsed)
        last_elapsed = self._initial_elapsed - 1
        while self._running:
            self.msleep(400)
            if not self._running:
                break
            elapsed = max(0, int(_time.monotonic() - start_mono))
            if elapsed == last_elapsed:
                continue
            last_elapsed = elapsed
            self._elapsed_cache = elapsed
            self.tick.emit(elapsed)
            if self._indefinite:
                continue
            with self._lock:
                total = self._total
            if elapsed >= total:
                break
        with self._lock:
            final_total = self._total
        if self._running and (not self._indefinite) and (last_elapsed >= final_total):
                    self.session_ended.emit()
    def stop_timer(self) -> None:
        self._running = False
class StationCard(QFrame):
    """Bitta PlayStation stoli kartasi — START/STOP, VIP, ichimlik, TV."""
    session_receipt = pyqtSignal(dict)
    def __init__(self, station_id: str, on_state_changed: Callable[[], None], parent=None, *, compact: bool=False, container=None, wake_restored_tvs: bool=False) -> None:
        super().__init__(parent)
        self.station_id = station_id
        self._compact = compact
        self._wake_restored_tvs = bool(wake_restored_tvs)
        self._port = make_station_card_port(container)
        self._on_state_changed = on_state_changed
        self._timer_thread = None
        self._session_db_id = None
        self._total_seconds = 0
        self._elapsed = 0
        self._busy = False
        self._vip_open = False
        self._block_thread_running = False
        self._pending_hard_block = None
        self._joystick_test_active = False
        self._joystick_count = JOYSTICK_FREE_COUNT
        self._session_start_dt = None
        self._session_billing_rate = 0.0
        self._charges_cache = (0.0, 0.0)
        self._charges_cache_mono = 0.0
        self._hdmi_cached = None
        self._block_generation = 0
        self._suppress_block_until = 0.0
        self._booking = None
        self.setObjectName('StationCard')
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._ctx_menu_pos = None
        self._ctx_menu_timer = QTimer(self)
        self._ctx_menu_timer.setSingleShot(True)
        self._ctx_menu_timer.timeout.connect(self._open_delayed_context_menu)
        self.customContextMenuRequested.connect(self._on_context_menu_requested)
        self._preview_click_timer = QTimer(self)
        self._preview_click_timer.setSingleShot(True)
        self._preview_click_timer.timeout.connect(self._emit_monitor_preview_receipt)
        self.installEventFilter(self)
        self._cw = station_col_widths(compact)
        row = QHBoxLayout(self)
        v_pad = 4 if compact else 6
        row.setContentsMargins(0, v_pad, 14, v_pad)
        row.setSpacing(0)
        self._accent_bar = QLabel()
        self._accent_bar.setFixedWidth(4)
        self._accent_bar.setStyleSheet(f'background: {STATUS_FREE}; border-radius: 2px;')
        row.addWidget(self._accent_bar)
        row.addSpacing(12)
        self._title = QLabel(self._port.display_name(station_id))
        title_pt = 12 if compact else 15
        self._title.setFont(QFont('Rajdhani', title_pt, QFont.Weight.Bold))
        self._title.setStyleSheet(f'color: {STATUS_FREE}; letter-spacing: 1px;')
        self._title.setFixedWidth(self._cw['stol'])
        row.addWidget(self._title)
        holat = QWidget()
        holat_l = QHBoxLayout(holat)
        holat_l.setContentsMargins(0, 0, 0, 0)
        holat_l.setSpacing(6)
        holat_l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        act_sz = 28 if compact else 32
        self._start_btn = QPushButton('+')
        self._start_btn.setObjectName('CardStart')
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setFixedSize(act_sz, act_sz)
        self._start_btn.setToolTip('START — seans boshlash / vaqt qo\'shish')
        self._start_btn.clicked.connect(self._on_start_clicked)
        holat_l.addWidget(self._start_btn)
        self._check_btn = QPushButton('✓')
        self._check_btn.setObjectName('CardVipCheck')
        self._check_btn.setFont(QFont('Segoe UI', 12 if compact else 15, QFont.Weight.Bold))
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.setFixedSize(act_sz, act_sz)
        self._check_btn.setToolTip('VIP: yangi hisob / davom etish')
        self._check_btn.setStyleSheet(f'QPushButton {{ color: {COL_GREEN}; background: transparent; border: none; }}QPushButton:hover {{ color: {GOLD_COLOR}; }}')
        self._check_btn.setVisible(False)
        self._check_btn.clicked.connect(self._on_holat_check_clicked)
        holat_l.addWidget(self._check_btn)
        self._drink_btn = QPushButton('🛒')
        self._drink_btn.setObjectName('CardDrink')
        self._drink_btn.setFont(QFont('Segoe UI Emoji', 12 if compact else 14))
        self._drink_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drink_btn.setFixedSize(act_sz, act_sz)
        self._drink_btn.setToolTip('Ichimliklar / market buyurtmasi')
        self._drink_btn.clicked.connect(self._on_drink_clicked)
        self._drink_btn.setVisible(False)
        holat_l.addWidget(self._drink_btn)
        holat.setFixedWidth(self._cw['holat'])
        row.addWidget(holat)
        def _make_col(color: str, *, mono: bool=False, bold: bool=True) -> QLabel:
            lbl = QLabel('—')
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            family = 'Consolas' if mono else 'Segoe UI'
            pt = (11 if compact else 13) if mono else 10 if compact else 12
            lbl.setFont(QFont(family, pt, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            lbl.setStyleSheet(f'color: {color};')
            return lbl
        self._col_started = _make_col(TEXT_SECONDARY, mono=True)
        self._col_played = _make_col(COL_CYAN, mono=True)
        self._col_ps = _make_col(COL_BLUE)
        self._col_goods = _make_col(COL_RED)
        self._col_total = _make_col(COL_GREEN)
        for w in [self._col_started, self._col_played, self._col_ps, self._col_goods, self._col_total]:
            row.addWidget(w, 1)
        right_box = QWidget()
        right_box.setFixedWidth(right_cluster_width(compact))
        right_row = QHBoxLayout(right_box)
        right_row.setContentsMargins(0, 0, 0, 0)
        right_row.setSpacing(0)
        right_row.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(right_box)
        side_btn_css = f"QPushButton {{  background: {BG_HEADER};  color: {TEXT_SECONDARY};  border: 1px solid {BORDER_COLOR};  border-radius: 8px;  padding: {('4px 8px' if compact else '6px 10px')};  font-weight: bold;}}QPushButton:hover {{  background: {BG_CARD_HOVER};  color: {TEXT_PRIMARY};  border: 1px solid {ACCENT};}}QPushButton:disabled {{  color: {TEXT_MUTED};  border: 1px solid {BORDER_COLOR};}}"
        self.btn_ovoz = QPushButton('🔊')
        self.btn_ovoz.setMinimumWidth(36 if compact else 42)
        self.btn_ovoz.setFont(QFont('Segoe UI', 9 if compact else 11))
        self.btn_ovoz.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ovoz.setToolTip('TV ovozini boshqarish')
        self.btn_ovoz.setStyleSheet(side_btn_css)
        self.btn_ovoz.clicked.connect(self._on_ovoz_clicked)
        self.btn_jostik = QPushButton('JOY')
        self.btn_jostik.setFont(QFont('Rajdhani', 8 if compact else 10, QFont.Weight.Bold))
        self.btn_jostik.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_jostik.setToolTip('Jostik qo\'shish (2 tadan ortig\'i pullik)')
        self.btn_jostik.setStyleSheet(side_btn_css)
        self.btn_jostik.setMinimumWidth(54 if compact else 62)
        self.btn_jostik.clicked.connect(self._on_joystick_clicked)
        self._hdmi_lbl = QLabel('')
        self._hdmi_lbl.setFont(QFont('Rajdhani', 8 if compact else 10, QFont.Weight.Bold))
        self._hdmi_lbl.setStyleSheet(f'color: {TEXT_SECONDARY};')
        self._hdmi_lbl.setVisible(False)
        self._stop_btn = QPushButton('Stop')
        self._stop_btn.setObjectName('CardStop')
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setFixedHeight(28 if compact else 32)
        self._stop_btn.setMinimumWidth(64 if compact else 76)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self.btn_transfer = QPushButton()
        self.btn_transfer.setObjectName('CardTransfer')
        transfer_sz = 24 if compact else 28
        self.btn_transfer.setFixedSize(transfer_sz, transfer_sz)
        self.btn_transfer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_transfer.setToolTip('Qolgan vaqt yoki VIP seansni boshqa bo\'sh stolga ko\'chirish')
        icon_path = _resource_path(TRANSFER_ICON_FILE)
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                self.btn_transfer.setIcon(QIcon(pix.scaled(transfer_sz - 8, transfer_sz - 8, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
                self.btn_transfer.setIconSize(QSize(transfer_sz - 10, transfer_sz - 10))
        else:
            self.btn_transfer.setText('⇄')
            self.btn_transfer.setFont(QFont('Segoe UI', 10 if compact else 12))
        self.btn_transfer.setStyleSheet(f'QPushButton#CardTransfer {{  background: {BG_HEADER};  border: 1px solid {BORDER_COLOR};  border-radius: 6px; padding: 0;}}QPushButton#CardTransfer:hover {{  background: {BG_CARD_HOVER};  border: 1px solid {ACCENT};}}')
        self.btn_transfer.clicked.connect(self._on_transfer_clicked)
        self.btn_transfer.setVisible(False)
        chevron = QLabel('›')
        chevron.setFont(QFont('Segoe UI', 14 if compact else 18, QFont.Weight.Bold))
        chevron.setStyleSheet(f'color: {TEXT_MUTED};')
        chevron.setFixedWidth(16)
        right_row.addWidget(self._stop_btn)
        right_row.addSpacing(12)
        right_row.addWidget(self.btn_ovoz)
        right_row.addSpacing(10)
        right_row.addWidget(self.btn_jostik)
        right_row.addWidget(self._hdmi_lbl)
        right_row.addSpacing(10)
        right_row.addWidget(self.btn_transfer)
        right_row.addSpacing(6)
        right_row.addWidget(chevron)
        self._icon = self._accent_bar
        self._status = QLabel('BO\'SH', self)
        self._status.setVisible(False)
        self._timer_lbl = QLabel('00:00:00', self)
        self._timer_lbl.setVisible(False)
        self._vip_sum = QLabel('', self)
        self._vip_sum.setVisible(False)
        self._extra_spin = QDoubleSpinBox(self)
        self._extra_spin.setRange(0, 1000000000)
        self._extra_spin.setDecimals(0)
        self._extra_spin.valueChanged.connect(self._on_extra_spin_changed)
        self._extra_spin.setVisible(False)
        self.setFixedHeight(48 if compact else 58)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._refresh_style()
        self._refresh_columns()
        self._sync_action_buttons()
        self._restore_active_session()
        for child in self.findChildren(QWidget):
            try:
                child.installEventFilter(self)
            except Exception:
                pass
    def _refresh_columns(self) -> None:
        """Jadval ustunlari qiymatlarini joriy holatga ko\'ra yangilash."""
        if not self._busy:
            for lbl in [self._col_started, self._col_played, self._col_ps, self._col_goods, self._col_total]:
                lbl.setText('—')
            return None
        else:
            started = '—'
            if self._session_start_dt is not None:
                started = self._session_start_dt.strftime('%H:%M')
            self._col_started.setText(started)
            if self._vip_open:
                play_secs = max(int(self._elapsed or 0), self._wall_elapsed_seconds(self._session_start_dt))
                if play_secs > int(self._elapsed or 0):
                    self._elapsed = play_secs
                self._col_played.setText(self._format_seconds(play_secs))
            else:
                rem = max(0, self._total_seconds - self._elapsed)
                self._col_played.setText(self._format_seconds(rem))
            ps_amount = self._ps_live_amount()
            goods_total, joystick_total = self._session_goods_joy()
            extra = self._extra_amount()
            from app.core.money import round_to_thousand
            ps_show = round_to_thousand(ps_amount + joystick_total + extra)
            goods_show = round_to_thousand(goods_total)
            total = ps_show + goods_show
            self._col_ps.setText(f'{ps_show:,.0f}')
            self._col_goods.setText(f'{goods_show:,.0f}')
            self._col_total.setText(f'{total:,.0f}')
    def _invalidate_charges_cache(self) -> None:
        self._charges_cache_mono = 0.0
    def _session_goods_joy(self, *, force: bool=False) -> tuple[float, float]:
        """Tovar/jostik: 0.8s kesh — har soniya SQLite ochilmasin."""
        import time
        now = time.monotonic()
        if (not force) and self._session_db_id is not None and (now - float(self._charges_cache_mono or 0)) < 0.8:
            return self._charges_cache
        goods_total = 0.0
        joystick_total = 0.0
        if self._session_db_id is not None:
            try:
                import database as _db
                goods_total, joystick_total = _db.split_session_charges(self.station_id, self._session_db_id)
            except Exception:
                try:
                    drink_total = self._port.drink_total(self.station_id, self._session_db_id)
                    joystick_total = self._port.joystick_total(self.station_id, self._session_db_id)
                    buy = 0.0
                    try:
                        buy = float(_db.get_session_buyurtma_total(self.station_id, self._session_db_id) or 0)
                    except Exception:
                        buy = 0.0
                    goods_total = max(0.0, float(drink_total) - float(joystick_total) - buy)
                except Exception:
                    goods_total = 0.0
                    joystick_total = 0.0
        self._charges_cache = (float(goods_total), float(joystick_total))
        self._charges_cache_mono = now
        return self._charges_cache
    def _arm_unblock_protection(self) -> None:
        """START dan keyin sticky bloklash overlay ni qayta yopmasin."""
        import time
        self._block_generation += 1
        self._suppress_block_until = time.time() + 60.0
    def _register_tv_session_gate(self) -> None:
        """Faol seans/JOSTIK: TV boot gate qayta bloklamasin."""
        import tv_handler
        settings = self._port.tv_settings(self.station_id)
        if settings.tv_ip:
            try:
                tv_handler.register_tv_session(settings.tv_ip, station_id=self.station_id)
            except Exception as e:
                logging.getLogger('tv').warning('Gate register %s: %s', self.station_id, e)
    def _unregister_tv_session_gate(self) -> None:
        import tv_handler
        settings = self._port.tv_settings(self.station_id)
        if settings.tv_ip:
            try:
                tv_handler.unregister_tv_session(settings.tv_ip, station_id=self.station_id)
            except Exception as e:
                logging.getLogger('tv').warning('Gate unregister %s: %s', self.station_id, e)
    def _re_block_if_free(self) -> None:
        """Bo\'sh stollar uchun bloklash (tez rejim). Band stolga tegmaydi."""
        import time
        if self._busy or self._joystick_test_active or self._block_thread_running:
            return None
        else:
            if time.time() < self._suppress_block_until:
                return
            else:
                settings = self._port.tv_settings(self.station_id)
                if not settings.tv_ip:
                    return
                else:
                    self._run_block_tv_async(settings, quick=True)
    def _run_block_tv_async(self, settings, *, quick: bool=True, ignore_busy: bool=False) -> None:
        """TV o'chirish/bloklash — parallel chaqiriqlarni oldini olish bilan."""
        import threading
        import time
        if self._block_thread_running:
            if ignore_busy:
                self._pending_hard_block = (settings, quick)
            return
        gen = self._block_generation
        self._block_thread_running = True

        def _runner() -> None:
            try:
                if gen != self._block_generation:
                    return
                if time.time() < self._suppress_block_until:
                    return
                if not ignore_busy and self._busy:
                    return
                import tv_handler
                import tv_platforms
                host = tv_handler.normalize_tv_host(settings.tv_ip)
                if not ignore_busy and not tv_handler._should_lock_tv(host):
                    print(f'[TV] Skip block — stol START: {self.station_id} {host}')
                    return
                handler = TVHandler(settings.tv_ip, settings.tv_mac, settings.brand, settings.hdmi_input)
                if tv_platforms.is_webos_brand(settings.brand):
                    if tv_platforms.WEBOS_POWER_OFF_ON_STOP:
                        if ignore_busy:
                            handler.block_screen(quick=quick, force=True)
                        if gen != self._block_generation:
                            try:
                                handler.unblock_screen()
                            except Exception:
                                pass
                        return
                    if not ignore_busy and not tv_handler._should_lock_tv(host):
                        return
                    pc_ip, gate_url = handler._smart_tv_gate_context()
                    params = tv_platforms.build_launch_params(pc_ip, host, gate_url, action='lock', hdmi_input=int(settings.hdmi_input or 1))
                    tv_platforms.webos_ensure_lock(host, params)
                    if gen != self._block_generation:
                        try:
                            handler.unblock_screen()
                        except Exception:
                            pass
                    return
                if tv_platforms.is_smart_tv_brand(settings.brand):
                    if not ignore_busy and not tv_handler._should_lock_tv(host):
                        return
                handler.block_screen(quick=quick, force=ignore_busy)
                if gen != self._block_generation:
                    try:
                        handler.unblock_screen()
                    except Exception:
                        pass
            finally:
                self._block_thread_running = False
                pending = self._pending_hard_block
                if pending is not None:
                    self._pending_hard_block = None
                    s, q = pending
                    self._run_block_tv_async(s, quick=q, ignore_busy=True)

        threading.Thread(target=_runner, daemon=True).start()

    def _wake_and_unblock_tv_async(self) -> None:
        """START: WOL + VIDAA ekranni yonish (fake_sleep)."""
        import threading
        settings = self._port.tv_settings(self.station_id)
        if not settings.tv_ip:
            return
        try:
            handler = TVHandler(settings.tv_ip, settings.tv_mac, settings.brand, settings.hdmi_input)

            def _runner() -> None:
                try:
                    handler.unblock_screen()
                except Exception as e:
                    logging.getLogger('tv').warning('Unblock %s: %s', self.station_id, e)

            threading.Thread(target=_runner, daemon=True).start()
        except Exception as e:
            logging.getLogger('tv').warning('Unblock thread %s: %s', self.station_id, e)
    def _refresh_style(self):
        """Holatga qarab qator uslubi (qorong\'i fon, rangli aksent)."""
        busy = self._busy
        if self._booking:
            accent = STATUS_BOOKED
        else:
            if busy and self._vip_open:
                accent = GOLD_COLOR
            else:
                if busy:
                    accent = STATUS_BUSY
                else:
                    accent = STATUS_FREE
        self._accent_bar.setStyleSheet(f'background: {accent}; border-radius: 2px;')
        self._title.setStyleSheet(f'color: {accent}; letter-spacing: 1px;')
        booked = bool(self._booking)
        card_bg = '#FEF9C3' if booked else BG_CARD
        card_border = '#FACC15' if booked else BORDER_COLOR
        hover_bg = '#FEF08A' if booked else BG_CARD_HOVER
        self.setStyleSheet(f'''
            QFrame#StationCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            QFrame#StationCard:hover {{
                background-color: {hover_bg};
            }}
            QPushButton#CardStart:enabled {{
                background-color: rgba(39, 208, 124, 0.16); color: {COL_GREEN};
                border: 1px solid rgba(39, 208, 124, 0.55);
                border-radius: 8px; font-size: 18px; font-weight: bold; padding: 0;
            }}
            QPushButton#CardStart:enabled:hover {{
                background-color: rgba(39, 208, 124, 0.28);
            }}
            QPushButton#CardStart:disabled {{
                background-color: {BG_HEADER}; color: {TEXT_MUTED};
                border: 1px solid {BORDER_COLOR}; border-radius: 8px; padding: 0;
            }}
            QPushButton#CardDrink {{
                background-color: rgba(34, 211, 238, 0.16); color: {ACCENT};
                border: 1px solid rgba(34, 211, 238, 0.55); border-radius: 8px;
                font-size: 16px; font-weight: bold; padding: 0;
            }}
            QPushButton#CardDrink:hover {{
                background-color: rgba(34, 211, 238, 0.30);
                border: 1px solid {ACCENT};
            }}
            QPushButton#CardStop:enabled {{
                background-color: rgba(255, 90, 110, 0.16); color: {COL_RED};
                border: 1px solid rgba(255, 90, 110, 0.55);
                border-radius: 8px; font-weight: bold; padding: 0;
            }}
            QPushButton#CardStop:enabled:hover {{
                background-color: rgba(255, 90, 110, 0.30);
            }}
        ''')
    def _set_status(self, text: str, color: str) -> None:
        """Holat o\'zgarganda aksent va ustunlarni yangilash."""
        self._status.setText(text)
        self._apply_title_text()
        self._refresh_style()
        self._refresh_columns()
    def _sync_action_buttons(self) -> None:
        busy = self._busy
        self._start_btn.setVisible(not busy)
        self._start_btn.setEnabled(not busy or not self._vip_open)
        self._check_btn.setVisible(busy)
        self._check_btn.setEnabled(busy and self._vip_open)
        self._check_btn.setToolTip('VIP: Boshlash — hisobni yopib 0 dan (TV o\'chmaydi)' if self._vip_open else 'VIP stol emas')
        self._drink_btn.setVisible(busy)
        self.btn_jostik.setVisible(busy)
        self.btn_jostik.setText(f'JOY ({self._joystick_count})')
        self.btn_jostik.setEnabled(busy)
        self._stop_btn.setVisible(busy)
        self._stop_btn.setEnabled(True)
        hdmi = int(self._hdmi_cached or 0)
        if busy and self._hdmi_cached is None:
            try:
                self._hdmi_cached = int(self._port.tv_settings(self.station_id).hdmi_input or 0)
                hdmi = int(self._hdmi_cached or 0)
            except Exception:
                self._hdmi_cached = 0
                hdmi = 0
        if busy and hdmi:
            self._hdmi_lbl.setText(f'⎙ {hdmi}')
            self._hdmi_lbl.setVisible(True)
        else:
            self._hdmi_lbl.setVisible(False)
        can_transfer = self._can_transfer_time()
        self.btn_transfer.setVisible(can_transfer)
        self.btn_transfer.setEnabled(can_transfer)
    def _remaining_seconds(self) -> int:
        if self._busy and self._vip_open:
            return 0
        else:
            return max(0, self._total_seconds - self._elapsed)
    def _can_transfer_time(self) -> bool:
        if not self._busy:
            return False
        else:
            if self._vip_open:
                return True
            else:
                return self._remaining_seconds() > 0
    def _on_transfer_clicked(self) -> None:
        is_vip = self._vip_open
        if is_vip:
            transfer_seconds = self._elapsed
        else:
            transfer_seconds = self._remaining_seconds()
            if transfer_seconds <= 0:
                QMessageBox.information(self, 'Vaqt yo\'q', 'Ko\'chirish uchun qolgan vaqt bo\'lishi kerak.')
                return
        win = self.window()
        if not hasattr(win, 'transfer_session_time'):
            return
        else:
            free = []
            for sid, card in win._cards.items():
                if sid != self.station_id and (not card._busy):
                        free.append((sid, card.display_name()))
            if not free:
                QMessageBox.information(self, 'Bo\'sh stol yo\'q', 'Ko\'chirish uchun boshqa bo\'sh (STOP holatidagi) stol bo\'lishi kerak.')
                return
            else:
                dlg = TransferTimeDialog(self.display_name(), transfer_seconds, free, self, is_vip=is_vip)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                else:
                    target_id = dlg.selected_station_id()
                    if target_id:
                        win.transfer_session_time(self.station_id, target_id)
    def _complete_transfer_out(self) -> None:
        """Manba stol: seansni yopish, TV bloklash, hisob-kitobsiz dialog."""
        if not self._busy:
            return
        else:
            elapsed = self._elapsed
            extra = self._extra_amount()
            goods_total = 0.0
            drink_total = 0.0
            if self._session_db_id is not None:
                try:
                    self._port.finalize_joystick_charges(self._session_db_id, trusted_now_naive())
                except Exception:
                    pass
                try:
                    import database as _db
                    goods_total, joy = _db.split_session_charges(self.station_id, self._session_db_id)
                    drink_total = goods_total + float(joy or 0)
                except Exception:
                    drink_total = self._port.drink_total(self.station_id, self._session_db_id)
                    goods_total = drink_total
                    joy = 0.0
            else:
                joy = 0.0
            self._stop_thread_only()
            settings = self._port.tv_settings(self.station_id)
            self._unregister_tv_session_gate()
            if settings.tv_ip:
                import threading
                handler = TVHandler(settings.tv_ip, settings.tv_mac, settings.brand, settings.hdmi_input)
                threading.Thread(target=lambda: handler.block_screen(force=True), daemon=True).start()
            time_rev = self._ps_final_amount(was_vip=bool(self._vip_open), start_dt=self._session_start_dt, end_dt=trusted_now_naive(), booked_seconds=int(self._total_seconds or 0), locked_rate=self._session_billing_rate or None)
            from app.core.money import round_to_thousand
            revenue = round_to_thousand(time_rev + float(joy or 0)) + round_to_thousand(extra + goods_total)
            minutes = max(1, (elapsed + 59) // 60) if elapsed else 0
            session_start_dt = self._session_start_dt
            session_end_dt = trusted_now_naive()
            if self._session_db_id is not None:
                self._port.end_session(self._session_db_id, minutes, revenue)
                self._session_db_id = None
            self._session_start_dt = None
            self._session_billing_rate = 0.0
            self._vip_open = False
            self._vip_sum.setVisible(False)
            self._busy = False
            self._elapsed = 0
            self._total_seconds = 0
            self._extra_spin.setValue(0)
            self._timer_lbl.setText('00:00:00')
            self._set_status('BO\'SH', STATUS_FREE)
            self._sync_action_buttons()
            self._refresh_style()
            self._on_state_changed()
    def _snapshot_transfer_payload(self) -> dict:
        """Ko\'chirish uchun holatni olish: taymerni to\'xtatadi, UI ni saqlab qoladi."""
        if not self._busy or self._session_db_id is None:
            return {}
        else:
            payload = {'session_db_id': self._session_db_id, 'elapsed': self._elapsed, 'total_seconds': self._total_seconds, 'session_start_dt': self._session_start_dt, 'billing_rate': float(self._session_billing_rate or 0), 'extra': self._extra_amount(), 'vip': bool(self._vip_open), 'joystick_count': int(self._joystick_count)}
            self._stop_thread_only()
            return payload
    def _finalize_transfer_out(self) -> None:
        """Muvaffaqiyatli ko\'chirishdan keyin manba stolni tozalash (seansni yakunlamaydi)."""
        settings = self._port.tv_settings(self.station_id)
        self._unregister_tv_session_gate()
        if settings.tv_ip:
            self._run_block_tv_async(settings, quick=True, ignore_busy=True)
        self._session_db_id = None
        self._session_start_dt = None
        self._session_billing_rate = 0.0
        self._vip_open = False
        self._vip_sum.setVisible(False)
        self._busy = False
        self._elapsed = 0
        self._total_seconds = 0
        self._joystick_count = JOYSTICK_FREE_COUNT
        self._extra_spin.setValue(0)
        self._timer_lbl.setText('00:00:00')
        self._set_status('BO\'SH', STATUS_FREE)
        self._sync_action_buttons()
        self._refresh_style()
        self._on_state_changed()
    def _resume_after_failed_transfer(self, payload: dict) -> None:
        """Dest qabul qilmasa — manba stol taymerini qayta ishga tushirish."""
        if payload and self._busy is False:
            return None
        else:
            if self._timer_thread is not None:
                return
            else:
                elapsed = max(0, int(payload.get('elapsed') or 0))
                if self._vip_open:
                    self._timer_thread = SessionTimer(0, self, indefinite=True, initial_elapsed=elapsed)
                    self._timer_thread.tick.connect(self._on_vip_tick)
                    self._timer_thread.start()
                    return
                else:
                    total_seconds = max(0, int(payload.get('total_seconds') or 0))
                    if total_seconds <= 0:
                        return
                    else:
                        self._elapsed = min(elapsed, total_seconds)
                        self._timer_thread = SessionTimer(total_seconds, self, indefinite=False, initial_elapsed=self._elapsed)
                        self._timer_thread.tick.connect(self._on_tick)
                        self._timer_thread.session_ended.connect(self._on_natural_end)
                        self._timer_thread.start()
    def _complete_vip_transfer_out(self) -> dict:
        """Orqaga moslik: snapshot (tozalash transfer_session_time da)."""
        if not self._busy or not self._vip_open:
            return {}
        else:
            return self._snapshot_transfer_payload()
    def _complete_timed_transfer_out(self) -> dict:
        """Orqaga moslik: snapshot (tozalash transfer_session_time da)."""
        if not self._busy or self._vip_open or self._session_db_id is None:
            return {}
        else:
            return self._snapshot_transfer_payload()
    def _accept_vip_transfer(self, payload: dict) -> bool:
        """Boshqa stoldan kelgan VIP seansni davom ettirish."""
        if self._busy or not payload:
            return False
        else:
            session_db_id = payload.get('session_db_id')
            elapsed = max(0, int(payload.get('elapsed') or 0))
            start_dt = payload.get('session_start_dt')
            extra = float(payload.get('extra') or 0)
            if session_db_id is None:
                return False
            else:
                if not self._port.transfer_session(int(session_db_id), self.station_id):
                    return False
                else:
                    settings = self._port.tv_settings(self.station_id)
                    self._stop_thread_only()
                    self._joystick_test_active = False
                    self._vip_open = True
                    self._total_seconds = 0
                    self._elapsed = elapsed
                    self._busy = True
                    self._session_start_dt = start_dt if isinstance(start_dt, datetime) else trusted_now_naive()
                    self._session_db_id = int(session_db_id)
                    try:
                        self._session_billing_rate = float(payload.get('billing_rate') or 0)
                    except Exception:
                        self._session_billing_rate = 0.0
                    if self._session_billing_rate <= 0:
                        from app.core.ps_billing import resolve_billing_rate
                        self._session_billing_rate = resolve_billing_rate(self.station_id, self._session_start_dt, None)
                    self._joystick_count = int(payload.get('joystick_count') or JOYSTICK_FREE_COUNT + self._port.count_joystick_charges(self._session_db_id))
                    self._extra_spin.setValue(extra)
                    self._arm_unblock_protection()
                    self._register_tv_session_gate()
                    self._set_status('VIP', GOLD_COLOR)
                    self._vip_sum.setVisible(False)
                    self._update_vip_sum_label()
                    self._timer_lbl.setText(self._format_seconds(elapsed))
                    if settings.tv_ip:
                        self._wake_and_unblock_tv_async()
                    self._timer_thread = SessionTimer(0, self, indefinite=True, initial_elapsed=elapsed)
                    self._timer_thread.tick.connect(self._on_vip_tick)
                    self._timer_thread.start()
                    self._sync_action_buttons()
                    self._on_state_changed()
                    return True
    def _accept_timed_transfer(self, payload: dict) -> bool:
        """Boshqa stoldan kelgan vaqtli seansni davom ettirish (yangi seans ochilmaydi)."""
        if self._busy or not payload:
            return False
        else:
            session_db_id = payload.get('session_db_id')
            elapsed = max(0, int(payload.get('elapsed') or 0))
            total_seconds = max(0, int(payload.get('total_seconds') or 0))
            start_dt = payload.get('session_start_dt')
            extra = float(payload.get('extra') or 0)
            if session_db_id is None or total_seconds <= 0:
                return False
            else:
                if not self._port.transfer_session(int(session_db_id), self.station_id):
                    return False
                else:
                    settings = self._port.tv_settings(self.station_id)
                    self._stop_thread_only()
                    self._joystick_test_active = False
                    self._vip_open = False
                    self._total_seconds = total_seconds
                    self._elapsed = min(elapsed, total_seconds)
                    self._busy = True
                    self._session_start_dt = start_dt if isinstance(start_dt, datetime) else trusted_now_naive()
                    self._session_db_id = int(session_db_id)
                    try:
                        self._session_billing_rate = float(payload.get('billing_rate') or 0)
                    except Exception:
                        self._session_billing_rate = 0.0
                    if self._session_billing_rate <= 0:
                        from app.core.ps_billing import resolve_billing_rate
                        self._session_billing_rate = resolve_billing_rate(self.station_id, self._session_start_dt, None)
                    self._joystick_count = int(payload.get('joystick_count') or JOYSTICK_FREE_COUNT + self._port.count_joystick_charges(self._session_db_id))
                    self._extra_spin.setValue(extra)
                    self._arm_unblock_protection()
                    self._register_tv_session_gate()
                    self._vip_sum.setVisible(False)
                    self._set_status('BAND', STATUS_BUSY)
                    remaining = max(0, total_seconds - self._elapsed)
                    self._timer_lbl.setText(self._format_seconds(remaining))
                    if settings.tv_ip:
                        self._wake_and_unblock_tv_async()
                    self._timer_thread = SessionTimer(total_seconds, self, indefinite=False, initial_elapsed=self._elapsed)
                    self._timer_thread.tick.connect(self._on_tick)
                    self._timer_thread.session_ended.connect(self._on_natural_end)
                    self._timer_thread.start()
                    self._sync_action_buttons()
                    self._on_state_changed()
                    return True
    def _restore_active_session(self) -> None:
        """Dastur qayta ochilganda bazadagi active seansni real vaqt bo\'yicha tiklash."""
        row = self._port.active_session(self.station_id)
        if not row:
            return
        start_dt = parse_session_dt(row['start_time'])
        if start_dt is None:
            return
        try:
            elapsed = max(0, int((trusted_now_naive() - start_dt).total_seconds()))
            total_seconds = int(row.get('total_seconds') or 0)
            is_vip = bool(row.get('is_vip'))
            try:
                self._session_billing_rate = float(row.get('billing_rate') or 0)
            except Exception:
                self._session_billing_rate = 0.0
            if self._session_billing_rate <= 0:
                from app.core.ps_billing import resolve_billing_rate
                self._session_billing_rate = resolve_billing_rate(self.station_id, start_dt, None)
            if not is_vip and total_seconds <= 0:
                try:
                    self._port.end_session(int(row['id']), 0, 0)
                except Exception:
                    logging.getLogger('session').exception('Orphan seansni yopib bo\'lmadi: %s', row.get('id'))
                return None
            else:
                self._stop_thread_only()
                self._joystick_test_active = False
                self._session_db_id = int(row['id'])
                self._joystick_count = JOYSTICK_FREE_COUNT + self._port.count_joystick_charges(self._session_db_id)
                self._session_start_dt = start_dt
                self._elapsed = elapsed
                self._busy = True
                self._vip_open = is_vip
                self._total_seconds = 0 if is_vip else total_seconds
                if is_vip:
                    self._set_status('VIP', GOLD_COLOR)
                    self._vip_sum.setVisible(False)
                    self._timer_lbl.setText(self._format_seconds(elapsed))
                    self._update_vip_sum_label()
                    self._timer_thread = SessionTimer(0, self, indefinite=True, initial_elapsed=elapsed)
                    self._timer_thread.tick.connect(self._on_vip_tick)
                    self._timer_thread.start()
                else:
                    self._vip_sum.setVisible(False)
                    self._set_status('BAND', STATUS_BUSY)
                    self._timer_lbl.setText(self._format_seconds(max(0, total_seconds - elapsed)))
                    if elapsed >= total_seconds:
                        QTimer.singleShot(0, self._on_natural_end)
                    else:
                        self._timer_thread = SessionTimer(total_seconds, self, initial_elapsed=elapsed)
                        self._timer_thread.tick.connect(self._on_tick)
                        self._timer_thread.session_ended.connect(self._on_natural_end)
                        self._timer_thread.start()
                self._sync_action_buttons()
                self._refresh_style()
                self._on_state_changed()
                if self._busy:
                    self._arm_unblock_protection()
                    self._register_tv_session_gate()
                    if self._wake_restored_tvs:
                        settings = self._port.tv_settings(self.station_id)
                        if settings.tv_ip:
                            self._wake_and_unblock_tv_async()
        except Exception:
            return None
    def refresh_display_name(self) -> None:
        """Admin paneldan nom o\'zgarganda kartochka sarlavhasini yangilash."""
        self._apply_title_text()
    def set_booking(self, booking: Optional[dict]) -> None:
        """Faol bron: nom yonida vaqt + sariq holat (seans ochiq bo\'lsa ham)."""
        self._booking = booking
        self._apply_title_text()
        self._refresh_style()
    def _apply_title_text(self) -> None:
        base = self._port.display_name(self.station_id)
        if self._booking:
            when = str(self._booking.get('booking_time') or '')
            short = when
            if 'T' in when:
                date_part, time_part = when.split('T', 1)
                short = time_part[:5] if time_part else date_part
                try:
                    from datetime import date
                    if date_part != date.today().isoformat():
                        parts = date_part.split('-')
                        if len(parts) == 3:
                            short = f'{parts[2]}.{parts[1]} {time_part[:5]}'
                except Exception:
                    pass
            self._title.setText(f'{base} ({short})')
            self._title.setToolTip(f"Bron: {self._booking.get('client_name', '')} — {when}")
        else:
            self._title.setText(base)
            self._title.setToolTip('')
    def display_name(self) -> str:
        return self._port.display_name(self.station_id)
    def _on_extra_spin_changed(self, _value: float) -> None:
        if self._busy and self._vip_open:
                self._update_vip_sum_label()
    def _on_stop_clicked(self) -> None:
        if self._busy:
            self._stop_reset()
        else:
            self._block_tv_without_session_change()
    def _block_tv_without_session_change(self) -> None:
        """Seans yo\'qligida ham TV ni qora ekran + soat lock holatiga o\'tkazish."""
        settings = self._port.tv_settings(self.station_id)
        if not settings.tv_ip:
            QMessageBox.warning(self, 'TV sozlanmagan', f'{self.station_id} uchun Admin → TV sozlamalarida IP kiriting.')
            return
        else:
            try:
                import threading
                logging.getLogger('tv').info('STOP (bo\'sh) %s: ip=%s brand=%s hdmi=%s', self.station_id, settings.tv_ip, settings.brand, settings.hdmi_input)
                self._unregister_tv_session_gate()
                self._run_block_tv_async(settings, quick=True, ignore_busy=True)
                QMessageBox.information(self, 'STOP', f'{self.station_id} TV o\'chirilmoqda...')
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'TV ni bloklashda xatolik: {e}')
    def _on_drink_clicked(self) -> None:
        """Savat: to\'g\'ridan-to\'g\'ri ICHIMLIKLAR + MARKET paneli."""
        if not self._busy:
            QMessageBox.information(self, 'Ma\'lumot', 'Buyurtma qilish uchun avval stolni START tugmasini bosing.')
            return
        try:
            from app.ui.dialogs.combined_shop_panel import CombinedShopPanel
            CombinedShopPanel(self.station_id, self._session_db_id, self).exec()
            self._invalidate_charges_cache()
            self._refresh_columns()
            win = self.window()
            if hasattr(win, '_refresh_today_revenue_banner'):
                win._refresh_today_revenue_banner()
        except ImportError:
            QMessageBox.critical(self, 'Xatolik', 'Buyurtma moduli topilmadi.')
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', f'Buyurtmani ochishda xatolik: {str(e)}')
    def _on_start_clicked(self) -> None:
        """START: vaqt tanlash menyusi (VIP yoki tayyor variantlar)."""
        menu = QMenu(self)
        menu.setStyleSheet(f'\n            QMenu {{\n                background-color: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                border: 1px solid #444;\n                padding: 4px;\n            }}\n            QMenu::item:selected {{ background-color: #333; }}\n            ')
        if self._busy:
            if self._vip_open:
                QMessageBox.information(self, 'VIP', 'VIP seansga vaqt qo\'shib bo\'lmaydi (u allaqachon cheksiz).')
                return
            else:
                title_act = QAction('--- VAQT QO\'SHISH ---', self)
                title_act.setEnabled(False)
                menu.addAction(title_act)
                add_presets = [('+30 daqiqa', 1800), ('+45 daqiqa', 2700), ('+1 soat', 3600), ('+1.5 soat', 5400), ('+2 soat', 7200)]
                for title, seconds in add_presets:
                    act = QAction(title, self)
                    act.triggered.connect(lambda checked=False, s=seconds: self._add_time_to_session(s))
                    menu.addAction(act)
        else:
            act_vip = QAction('VIP (vaqt va summa avtomatik)', self)
            act_vip.triggered.connect(self._open_vip_start)
            menu.addAction(act_vip)
            menu.addSeparator()
            presets = [('30 daqiqa', 1800), ('45 daqiqa', 2700), ('1 soat', 3600), ('1 soat 15 daqiqa', 4500), ('1 soat 30 daqiqa', 5400), ('2 soat', 7200), ('3 soat', 10800)]
            for title, seconds in presets:
                act = QAction(title, self)
                act.triggered.connect(lambda checked=False, s=seconds: self._start_session(s))
                menu.addAction(act)
        pos = self._start_btn.mapToGlobal(self._start_btn.rect().bottomLeft())
        menu.exec(pos)
    def _add_time_to_session(self, seconds: int) -> None:
        """Mavjud seansga vaqt qo\'shish."""
        if not self._busy or not self._timer_thread:
            return None
        else:
            self._total_seconds += seconds
            self._timer_thread.add_time(seconds)
            if self._session_db_id is not None:
                self._port.update_session_total_seconds(self._session_db_id, self._total_seconds)
            QMessageBox.information(self, 'OK', f'{self.station_id} uchun {seconds // 60} daqiqa qo\'shildi.')
            self._on_state_changed()
    def _open_vip_start(self) -> None:
        dlg = VIPStartDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            self._start_vip_session()
    def _on_holat_check_clicked(self) -> None:
        """VIP stol ✓: yangi VIP hisob (TV o\'chmasdan) yoki bekor."""
        if not self._busy or not self._vip_open:
            return None
        else:
            self._open_vip_rollover_dialog()
    def _open_vip_rollover_dialog(self) -> None:
        """Boshlash = oldingi hisobni STOP kabi yozish + 0 dan VIP (TV yonib qoladi)."""
        dlg = VIPStartDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            self._rollover_vip_session()
    def _rollover_vip_session(self) -> None:
        """VIP hisobni yakunlash (monitor + daromad) va darhol yangi VIP 0 dan — TV tekin."""
        if not self._busy or not self._vip_open:
            return None
        else:
            self._finish_session(power_off=False, natural=False, restart_vip=True)
    @staticmethod
    def _format_seconds(seconds: int) -> str:
        """Saniyalarni HH:MM:SS formatiga o\'tkazish."""
        h = seconds // 3600
        m = seconds % 3600 // 60
        s = seconds % 60
        return f'{h:02d}:{m:02d}:{s:02d}'
    def _time_revenue_proportional(self, station_id: str, elapsed_seconds: int, start_dt: Optional[datetime]=None, *, lock_rate_at_start: Optional[bool]=None) -> float:
        """Orqaga moslik: tarif × soniya (qulflangan billing_rate)."""
        if elapsed_seconds <= 0:
            return 0.0
        else:
            from app.core.ps_billing import resolve_billing_rate, time_amount
            start = start_dt or self._session_start_dt
            rate = resolve_billing_rate(station_id, start, self._session_billing_rate or None)
            return round(time_amount(rate, int(elapsed_seconds)), 2)
    def _ps_live_amount(self) -> float:
        """Jonli PLAYSTATION ustuni — qulflangan tarif, bazaga har soniya bormaslik."""
        from app.core.ps_billing import time_amount, wall_seconds
        now = trusted_now_naive()
        seconds = wall_seconds(self._session_start_dt, now)
        rate = float(self._session_billing_rate or 0)
        if rate <= 0:
            from app.core.ps_billing import resolve_billing_rate
            rate = resolve_billing_rate(self.station_id, self._session_start_dt, None)
            self._session_billing_rate = rate
        return float(time_amount(rate, seconds))
    def _ps_final_amount(self, *, was_vip: bool, start_dt: Optional[datetime], end_dt: datetime, booked_seconds: int, locked_rate: Optional[float]=None) -> float:
        """STOP / rollover — yagona yakuniy PS summasi."""
        return float(playstation_amount(self.station_id, is_vip=was_vip, start=start_dt, end=end_dt, booked_seconds=booked_seconds, locked_rate=locked_rate if locked_rate is not None else self._session_billing_rate or None))
    def _extra_amount(self) -> float:
        return float(self._extra_spin.value())
    def eventFilter(self, obj, event) -> bool:
        """Chap bosish → chek (mijoz + operator 8s). Chap 2× → Buyurtma. O'ng 2× → chek."""
        from PyQt6.QtCore import QEvent
        if event is not None and self._busy and (self._session_db_id is not None):
            skip = {self._start_btn, self._drink_btn, getattr(self, 'btn_transfer', None), getattr(self, 'btn_jostik', None), getattr(self, '_check_btn', None)}
            is_btn = obj in skip or isinstance(obj, QPushButton)
            try:
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and (not is_btn):
                    try:
                        delay = int(QApplication.doubleClickInterval()) + 50
                    except Exception:
                        delay = 400
                    self._preview_click_timer.start(max(400, delay))
                elif event.type() == QEvent.Type.MouseButtonDblClick:
                    if is_btn:
                        return False
                    btn = event.button()
                    if btn == Qt.MouseButton.RightButton:
                        self._preview_click_timer.stop()
                        self._emit_monitor_preview_receipt()
                        return True
                    if btn == Qt.MouseButton.LeftButton:
                        self._preview_click_timer.stop()
                        self._open_buyurtma_dialog()
                        return True
            except Exception:
                pass
        return super().eventFilter(obj, event)
    def mouseDoubleClickEvent(self, event) -> None:
        """Chap: Buyurtma. O\'ng: monitor cheki (TV ochilmaydi)."""
        try:
            if self._busy and self._session_db_id is not None and event is not None:
                if event.button() == Qt.MouseButton.RightButton:
                    self._emit_monitor_preview_receipt()
                    event.accept()
                    return
                if event.button() == Qt.MouseButton.LeftButton:
                    self._open_buyurtma_dialog()
                    event.accept()
                    return
        except Exception:
            logging.getLogger('tv').exception('Double-click xato')
        super().mouseDoubleClickEvent(event)
    def _emit_monitor_preview_receipt(self) -> None:
        """O\'ng 2×: joriy chek mijoz monitorida. TV YOQILMAYDI. Hisob 0 dan (elapsed)."""
        if not self._busy or self._session_db_id is None:
            return None
        else:
            try:
                self._ctx_menu_timer.stop()
                self._ctx_menu_pos = None
            except Exception:
                pass
            was_vip = bool(self._vip_open)
            extra = self._extra_amount()
            goods_total = 0.0
            joystick_total = 0.0
            buyurtma_total = 0.0
            order_items = []
            try:
                import database as _db
                goods_total, joystick_total = _db.split_session_charges(self.station_id, self._session_db_id)
                buyurtma_total = float(_db.get_session_buyurtma_total(self.station_id, self._session_db_id) or 0)
                grouped = self._port.session_orders_grouped(self._session_db_id, self.station_id)
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
                                img = _db.find_catalog_image(str(it.get('item_type') or ''), str(name), vol)
                            except Exception:
                                img = None
                        order_items.append({'name': display_name, 'size': size.strip(), 'count': cnt, 'unit': unit, 'total': line_total, 'image': img, 'item_type': str(it.get('item_type') or ''), 'note': str(name) if is_buyurtma else ''})
            except Exception:
                logging.getLogger('tv').exception('Chek tuzilmadi: %s', self.station_id)
                order_items = []
                goods_total = 0.0
                joystick_total = 0.0
                buyurtma_total = 0.0
            time_rev = self._ps_live_amount()
            from app.core.money import round_to_thousand
            ps_show = round_to_thousand(time_rev + joystick_total + extra)
            goods_show = round_to_thousand(goods_total)
            buy_show = round_to_thousand(buyurtma_total)
            billable = ps_show + goods_show
            total = billable + buy_show
            label_vip = ' (VIP)' if was_vip else ''
            try:
                self.session_receipt.emit({'title': 'Joriy hisob', 'station': f'{self.display_name()}{label_vip}', 'body_html': '', 'total': total, 'time_rev': ps_show, 'drink_total': goods_show, 'joystick_total': joystick_total, 'buyurtma_total': buy_show, 'extra': extra, 'order_items': order_items, 'duration_ms': 15000, 'customer_ms': 15000, 'preview': True, 'operator_ms': 8000, 'billable_total': billable})
            except Exception:
                logging.getLogger('tv').exception('Monitor preview yuborilmadi')
    def _open_buyurtma_dialog(self) -> None:
        if not self._busy or self._session_db_id is None:
            return None
        if getattr(self, '_buyurtma_dialog_open', False):
            return
        self._buyurtma_dialog_open = True
        try:
            dlg = BuyurtmaDialog(self.display_name(), self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            amount = dlg.amount()
            note = dlg.note()
            try:
                import database as _db
                _db.add_session_buyurtma(self.station_id, int(self._session_db_id), amount, note)
            except Exception as e:
                QMessageBox.critical(self, 'Buyurtma', str(e))
                return
            self._invalidate_charges_cache()
            if self._vip_open:
                self._update_vip_sum_label()
            self._refresh_columns()
            self._on_state_changed()
            try:
                win = self.window()
                if hasattr(win, '_refresh_customer_display'):
                    win._refresh_customer_display()
            except Exception:
                pass
            QMessageBox.information(self, 'Buyurtma', f"Qo'shildi: {amount:,.0f} so'm\n{note}\n\nJami summaga qo'shildi.")
        finally:
            self._buyurtma_dialog_open = False
    def _update_vip_sum_label(self) -> None:
        """VIP seans uchun summalar (yashirin label bo\'lsa hisoblanmasin)."""
        if not self._vip_sum.isVisible():
            return
        t = self._ps_live_amount()
        ex = self._extra_amount()
        goods_total, joystick_total = self._session_goods_joy()
        from app.core.money import round_to_thousand
        jami = round_to_thousand(t + ex + goods_total + joystick_total)
        self._vip_sum.setText(f'💰 {jami:,.0f} so\'m  (Vaqt {round_to_thousand(t + joystick_total):,.0f} + Ichimlik {round_to_thousand(goods_total):,.0f} + Qo\'shimcha {round_to_thousand(ex):,.0f})')
    def _resume_or_block_duplicate_start(self) -> bool:
        """Bazada ochiq seans qolgan bo\'lsa yangi yozuv ochmaslik."""
        if self._busy:
            return True
        else:
            row = self._port.active_session(self.station_id)
            if not row:
                return False
            else:
                self._restore_active_session()
                return bool(self._busy)
    def _start_vip_session(self, *, wake_tv: bool=True) -> None:
        if self._busy:
            QMessageBox.information(self, 'Band', f'{self.station_id} hozir band.')
            return
        else:
            if self._resume_or_block_duplicate_start():
                return
            else:
                try:
                    import threading
                    from app.core.network_time import get_network_time
                    threading.Thread(target=lambda: get_network_time().sync(force=False), daemon=True, name='net-time-sync').start()
                except Exception:
                    pass
                settings = self._port.tv_settings(self.station_id)
                self._stop_thread_only()
                self._joystick_test_active = False
                self._joystick_count = JOYSTICK_FREE_COUNT
                self._vip_open = True
                self._total_seconds = 0
                self._elapsed = 0
                self._busy = True
                self._session_start_dt = trusted_now_naive()
                self._arm_unblock_protection()
                self._register_tv_session_gate()
                if wake_tv and settings.tv_ip:
                        print(f'[DEBUG] START VIP: unblocking TV for {self.station_id}')
                        self._wake_and_unblock_tv_async()
                self._session_db_id = self._port.start_session(self.station_id, total_seconds=0, is_vip=True)
                try:
                    import database as _db
                    row = _db.get_session_by_id(int(self._session_db_id))
                    self._session_billing_rate = float((row or {}).get('billing_rate') or 0)
                except Exception:
                    from app.core.ps_billing import resolve_billing_rate
                    self._session_billing_rate = resolve_billing_rate(self.station_id, self._session_start_dt, None)
                self._set_status('VIP', GOLD_COLOR)
                self._vip_sum.setVisible(False)
                self._update_vip_sum_label()
                self._timer_lbl.setText('00:00:00')
                self._timer_thread = SessionTimer(0, self, indefinite=True)
                self._timer_thread.tick.connect(self._on_vip_tick)
                self._timer_thread.start()
                self._sync_action_buttons()
                self._on_state_changed()
                self._refresh_columns()
    def _on_context_menu_requested(self, pos) -> None:
        """O\'ng tugma: 2× bo\'lsa monitor cheki; aks holda menyu."""
        self._ctx_menu_pos = pos
        try:
            from PyQt6.QtWidgets import QApplication
            delay = int(QApplication.doubleClickInterval()) + 50
        except Exception:
            delay = 400
        self._ctx_menu_timer.start(max(250, delay))
    def _open_delayed_context_menu(self) -> None:
        pos = self._ctx_menu_pos
        self._ctx_menu_pos = None
        if pos is not None:
            self._show_menu(pos)
    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f'QMenu {{ background-color: {BG_CARD}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR}; padding: 4px; }}QMenu::item:selected {{ background-color: rgba(255,255,255,0.10); }}')
        if self._busy and (not self._vip_open):
            for title, seconds in [('+30 daqiqa', 1800), ('+1 soat', 3600), ('+2 soat', 7200)]:
                act = QAction(title, self)
                act.triggered.connect(lambda checked=False, s=seconds: self._add_time_to_session(s))
                menu.addAction(act)
            menu.addSeparator()
            astop = QAction('STOP — seansni yakunlash', self)
            astop.triggered.connect(self._stop_reset)
            menu.addAction(astop)
        else:
            a1 = QAction('Tezkor start: 1 soat', self)
            a1.triggered.connect(lambda: self._start_session(3600))
            a2 = QAction('Tezkor start: 2 soat', self)
            a2.triggered.connect(lambda: self._start_session(7200))
            a3 = QAction('Tezkor start: 3 soat', self)
            a3.triggered.connect(lambda: self._start_session(10800))
            ac = QAction('Maxsus vaqt...', self)
            ac.triggered.connect(self._custom_time)
            astop = QAction('STOP — bloklash (qora ekran + soat)', self)
            astop.triggered.connect(self._on_stop_clicked)
            menu.addAction(a1)
            menu.addAction(a2)
            menu.addAction(a3)
            menu.addSeparator()
            menu.addAction(ac)
            menu.addSeparator()
            menu.addAction(astop)
        menu.exec(self.mapToGlobal(pos))
    def _custom_time(self) -> None:
        val, ok = QInputDialog.getInt(self, 'Maxsus vaqt', 'Daqiqa kiriting:', value=60, min=1, max=1440)
        if ok:
            self._start_session(val * 60)
    def _start_session(self, seconds: int) -> None:
        if self._busy:
            QMessageBox.information(self, 'Band', f'{self.station_id} hozir band.')
            return
        else:
            if self._resume_or_block_duplicate_start():
                return
            else:
                try:
                    import threading
                    from app.core.network_time import get_network_time
                    threading.Thread(target=lambda: get_network_time().sync(force=False), daemon=True, name='net-time-sync').start()
                except Exception:
                    pass
                settings = self._port.tv_settings(self.station_id)
                self._stop_thread_only()
                self._joystick_test_active = False
                self._joystick_count = JOYSTICK_FREE_COUNT
                self._vip_open = False
                self._vip_sum.setVisible(False)
                self._total_seconds = seconds
                self._elapsed = 0
                self._busy = True
                self._session_start_dt = trusted_now_naive()
                self._arm_unblock_protection()
                self._register_tv_session_gate()
                if settings.tv_ip:
                    logging.getLogger('tv').info('START %s: ip=%s brand=%s hdmi=%s', self.station_id, settings.tv_ip, settings.brand, settings.hdmi_input)
                    self._wake_and_unblock_tv_async()
                self._session_db_id = self._port.start_session(self.station_id, total_seconds=seconds, is_vip=False)
                try:
                    import database as _db
                    row = _db.get_session_by_id(int(self._session_db_id))
                    self._session_billing_rate = float((row or {}).get('billing_rate') or 0)
                except Exception:
                    from app.core.ps_billing import resolve_billing_rate
                    self._session_billing_rate = resolve_billing_rate(self.station_id, self._session_start_dt, None)
                self._set_status('BAND', STATUS_BUSY)
                self._timer_lbl.setText(self._format_seconds(seconds))
                self._timer_thread = SessionTimer(seconds, self)
                self._timer_thread.tick.connect(self._on_tick)
                self._timer_thread.session_ended.connect(self._on_natural_end)
                self._timer_thread.start()
                self._sync_action_buttons()
                self._on_state_changed()
    def _on_vip_tick(self, elapsed: int) -> None:
        """VIP seans uchun tick handler - 00:00:00 dan count up"""
        if not self._busy or not self._vip_open:
            return None
        else:
            sender = self.sender()
            if sender is not None and sender is not self._timer_thread:
                    return
            synced = max(int(elapsed or 0), int(self._elapsed or 0), self._wall_elapsed_seconds(self._session_start_dt))
            self._elapsed = synced
            self._timer_lbl.setText(self._format_seconds(synced))
            self._update_vip_sum_label()
            self._refresh_columns()
    def _on_tick(self, elapsed: int) -> None:
        """Fixed seans uchun tick handler"""
        if self._busy and self._vip_open:
            return None
        else:
            sender = self.sender()
            if sender is not None and sender is not self._timer_thread:
                    return
            wall = self._wall_elapsed_seconds(self._session_start_dt)
            synced = max(int(elapsed or 0), min(wall, int(self._total_seconds or 0) + 5))
            self._elapsed = synced
            rem = max(0, self._total_seconds - synced)
            self._timer_lbl.setText(self._format_seconds(rem))
            self._refresh_columns()
    def _on_ovoz_clicked(self) -> None:
        """OVOZ tugmasi bosilganda - volume dialog EKRAN markazida ochish."""
        container = getattr(self._port, '_c', None)
        dialog = VolumeDialog(self.station_id, self, container=container)
        try:
            screen = QApplication.primaryScreen()
            geo = screen.availableGeometry() if screen else None
            if geo is not None:
                dialog.adjustSize()
                dialog.move(geo.center() - dialog.rect().center())
        except Exception:
            pass
        dialog.exec()
    def _on_joystick_clicked(self) -> None:
        """JOSTIK qo\'shish: bepul 2 tadan ortiq har bir jostik soatbay hisoblanadi.\n\n        Boshlanishda 2 ta jostik bepul (JOY(2)). Qo\'shimcha jostik qo\'shilganda\n        to\'lov shu vaqtdan STOP gacha: (soatlik jostik narxi × o\'tgan soat).\n        Masalan: 3000/soat, 30 daqiqa → 1500 so\'m (+ stol vaqti alohida).\n        """
        if not self._busy:
            return
        else:
            price = self._port.joystick_price()
            next_count = self._joystick_count + 1
            try:
                self._port.add_joystick_charge(self.station_id, price, self._session_db_id)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', f'Jostik qo\'shishda xatolik: {e}')
                return None
            self._joystick_count = next_count
            self._invalidate_charges_cache()
            self._sync_action_buttons()
            self._refresh_columns()
            try:
                win = self.window()
                if hasattr(win, '_refresh_today_revenue_banner'):
                    win._refresh_today_revenue_banner()
            except Exception:
                pass
            QMessageBox.information(self, 'Jostik qo\'shildi', f'{self.display_name()}: {self._joystick_count}-jostik berildi.\nQo\'shimcha jostik: {price:,.0f} so\'m/soat (to\'lov o\'ynagan vaqt bo\'yicha hisoblanadi).')
    def _on_natural_end(self) -> None:
        self._finish_session(power_off=True, natural=True)
    def _stop_reset(self) -> None:
        if not self._busy:
            QMessageBox.information(self, 'Bo\'sh', 'Bu stol allaqachon bo\'sh.')
            return
        else:
            self._finish_session(power_off=True, natural=False)
    def _stop_thread_only(self) -> None:
        thread = self._timer_thread
        self._timer_thread = None
        if thread:
            try:
                thread.tick.disconnect()
            except TypeError:
                pass
            try:
                thread.session_ended.disconnect()
            except TypeError:
                pass
            thread.stop_timer()
            if thread.isRunning() and (not thread.wait(200)):
                    logging.getLogger('tv').warning('SessionTimer %s tez to\'xtamadi', self.station_id)
            thread.deleteLater()
    def _wall_elapsed_seconds(self, start_dt: Optional[datetime], end_dt: Optional[datetime]=None) -> int:
        """START→hozir (yoki end) — ishonchli o\'tgan soniyalar."""
        end = end_dt if end_dt is not None else trusted_now_naive()
        return _ps_wall_seconds(start_dt, end)
    def _resolve_session_start_dt(self, session_db_id: Optional[int], fallback: Optional[datetime]) -> Optional[datetime]:
        """STOP hisobi uchun bazadagi start_time (xotira adashsa ham)."""
        if session_db_id is not None:
            try:
                import database as _db
                row = _db.get_session_by_id(int(session_db_id))
                if row and row.get('start_time'):
                    parsed = parse_session_dt(row['start_time'])
                    if parsed is not None:
                        try:
                            br = float(row.get('billing_rate') or 0)
                            if br > 0:
                                self._session_billing_rate = br
                        except Exception:
                            pass
                        return parsed
            except Exception:
                logging.getLogger('billing').warning('session start_time o\'qilmadi id=%s', session_db_id, exc_info=True)
        return fallback
    def _billable_seconds(self, *, was_vip: bool, timer_elapsed: int, start_dt: Optional[datetime], end_dt: datetime, total_seconds: int) -> int:
        """Hisob soniyalari — faqat START→STOP (o'ynagan vaqt)."""
        _ = timer_elapsed
        return _ps_billable_seconds(is_vip=was_vip, start=start_dt, end=end_dt, booked_seconds=int(total_seconds or 0))
    def _finish_session(self, power_off: bool, natural: bool, *, restart_vip: bool=False) -> None:
        if not self._busy:
            return
        else:
            was_vip = self._vip_open
            timer_elapsed = int(self._elapsed or 0)
            extra = self._extra_amount()
            total_seconds_snap = int(self._total_seconds or 0)
            session_db_id = self._session_db_id
            locked_rate_snap = float(self._session_billing_rate or 0)
            session_end_dt = trusted_now_naive()
            session_start_dt = self._resolve_session_start_dt(session_db_id, self._session_start_dt)
            if locked_rate_snap <= 0:
                locked_rate_snap = float(self._session_billing_rate or 0)
            calc_time = self._billable_seconds(was_vip=was_vip, timer_elapsed=timer_elapsed, start_dt=session_start_dt, end_dt=session_end_dt, total_seconds=total_seconds_snap)
            elapsed = calc_time
            settings = self._port.tv_settings(self.station_id)
            logging.getLogger('tv').info('STOP %s: ip=%s brand=%s hdmi=%s restart_vip=%s power_off=%s', self.station_id, settings.tv_ip, settings.brand, settings.hdmi_input, restart_vip, power_off)
            if restart_vip:
                self._arm_unblock_protection()
            else:
                self._unregister_tv_session_gate()
                self._suppress_block_until = 0.0
                self._block_generation += 1
                if power_off and settings.tv_ip:
                    print(f'[DEBUG] Calling TV block_screen for {settings.brand} TV at {settings.tv_ip}')
                    self._run_block_tv_async(settings, quick=True, ignore_busy=True)
                else:
                    if power_off:
                        print(f'[DEBUG] No TV IP configured for {self.station_id}')
            self._stop_thread_only()
            self._session_db_id = None
            self._session_start_dt = None
            self._session_billing_rate = 0.0
            self._vip_open = False
            self._vip_sum.setVisible(False)
            self._busy = False
            self._elapsed = 0
            self._total_seconds = 0
            self._extra_spin.setValue(0)
            self._timer_lbl.setText('00:00:00')
            self._set_status('BO\'SH', STATUS_FREE)
            self._sync_action_buttons()
            self._on_state_changed()
            drink_total = 0.0
            joystick_total = 0.0
            buyurtma_total = 0.0
            goods_total = 0.0
            order_lines = []
            order_items = []
            if session_db_id is not None:
                try:
                    self._port.finalize_joystick_charges(session_db_id, session_end_dt)
                except Exception:
                    pass
                try:
                    import database as _db
                    goods_total, joystick_total = _db.split_session_charges(self.station_id, session_db_id)
                    buyurtma_total = float(_db.get_session_buyurtma_total(self.station_id, session_db_id) or 0)
                    drink_total = goods_total + joystick_total
                    grouped = self._port.session_orders_grouped(session_db_id, self.station_id)
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
                            size = ''
                        else:
                            if is_buyurtma:
                                size = ''
                            else:
                                size = f' {vol:g}g' if is_market and vol else f' {vol:g}L' if vol and (not is_market) else ''
                        display_name = f'Buyurtma: {name}' if is_buyurtma else str(name)
                        if not is_joy:
                            order_lines.append(f'&nbsp;&nbsp;• {display_name}{size} — {cnt} x {unit:,.0f} = {line_total:,.0f} so\'m')
                            img = None
                            if not is_buyurtma:
                                try:
                                    img = _db.find_catalog_image(str(it.get('item_type') or ''), str(name), vol)
                                except Exception:
                                    img = None
                            order_items.append({'name': display_name, 'size': size.strip(), 'count': cnt, 'unit': unit, 'total': line_total, 'image': img, 'item_type': str(it.get('item_type') or ''), 'note': str(name) if is_buyurtma else ''})
                except Exception:
                    logging.getLogger('billing').exception('Chek tuzilmadi: %s', self.station_id)
                    order_lines = []
                    order_items = []
                    drink_total = 0.0
                    joystick_total = 0.0
                    buyurtma_total = 0.0
                    goods_total = 0.0
            time_rev = self._ps_final_amount(was_vip=was_vip, start_dt=session_start_dt, end_dt=session_end_dt, booked_seconds=total_seconds_snap, locked_rate=locked_rate_snap or None)
            from app.core.money import round_to_thousand
            goods_bill = round_to_thousand(goods_total)
            buy_show = round_to_thousand(buyurtma_total)
            ps_bill = round_to_thousand(time_rev + joystick_total + extra)
            revenue = ps_bill + goods_bill
            time_rev = ps_bill
            minutes = max(1, (elapsed + 59) // 60) if elapsed else 0
            if session_db_id is not None:
                try:
                    self._port.end_session(session_db_id, minutes, revenue)
                except Exception as e:
                    logging.getLogger('tv').warning('end_session: %s', e)
                try:
                    logging.getLogger('billing').info('STOP bill %s: vip=%s calc_s=%s timer_s=%s wall_s=%s rate=%.0f rate_rev=%.0f extra=%.0f drinks=%.0f buyurtma=%.0f total=%.0f start=%s end=%s restart_vip=%s', self.station_id, was_vip, calc_time, timer_elapsed, self._wall_elapsed_seconds(session_start_dt, session_end_dt), locked_rate_snap, time_rev, extra, goods_bill, buy_show, revenue, session_start_dt, session_end_dt, restart_vip)
                except Exception:
                    pass
            label_vip = ' (VIP)' if was_vip else ''
            station_title = f'{self.display_name()}{label_vip}'
            detail_lines = [f'Vaqt: {time_rev:,.0f} so\'m']
            if order_lines:
                detail_lines.append('Olingan mahsulotlar:')
                detail_lines.extend(order_lines)
                detail_lines.append(f'<span style=\'color:{TEXT_SECONDARY};\'>Mahsulotlar jami: {goods_bill:,.0f} so\'m</span>')
            else:
                detail_lines.append('Mahsulotlar: yo\'q')
            if extra > 0:
                detail_lines.append(f'Qo\'shimcha: {extra:,.0f} so\'m')
            body_html = '<br>'.join(detail_lines)
            if restart_vip:
                title = 'VIP — oldingi hisob'
            else:
                if natural:
                    title = 'Seans tugadi'
                    body_html += '<br><br>Vaqt tugadi. TV bloklandi.'
                else:
                    title = 'STOP — hisob'
            try:
                self.session_receipt.emit({'title': title, 'station': station_title, 'body_html': body_html, 'total': revenue + buy_show, 'time_rev': time_rev, 'drink_total': goods_bill, 'joystick_total': joystick_total, 'buyurtma_total': buy_show, 'extra': extra, 'order_items': order_items, 'duration_ms': 20000, 'rollover': bool(restart_vip), 'preview': bool(restart_vip), 'billable_total': revenue})
            except Exception:
                logging.getLogger('tv').exception('Mijoz ekrani hisoboti yuborilmadi')
            try:
                win = self.window()
                if hasattr(win, '_refresh_today_revenue_banner'):
                    win._refresh_today_revenue_banner()
            except Exception:
                pass
            if restart_vip:
                try:
                    self._start_vip_session(wake_tv=False)
                except Exception:
                    logging.getLogger('billing').exception('VIP rollover start xato: %s', self.station_id)
    def refresh_after_settings(self) -> None:
        """TV sozlamalari o\'zgarganda (stol kartasi boshqa UI talab qilmasa)."""
        return