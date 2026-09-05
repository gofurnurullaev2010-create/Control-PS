from __future__ import annotations
import logging
import re
import threading
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout
import database as db
from app.ui.dialogs.colors import ACCENT, ACCENT_HOVER, BG_CARD, BG_MAIN, TEXT_PRIMARY, TEXT_SECONDARY
logger = logging.getLogger(__name__)
class TVSettingsDialog(QDialog):
    _pin_requested = pyqtSignal()
    _pair_done = pyqtSignal(bool, str)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pin_event = threading.Event()
        self._pin_value = ''
        self._pair_busy = False
        self._pin_requested.connect(self._on_pin_requested)
        self._pair_done.connect(self._on_pair_done)
        self.setWindowTitle('TV sozlamalari (har bir stol)')
        self.resize(480, 420)
        self.setStyleSheet(''.join(f'\n            QDialog {{\n                background: {BG_MAIN};\n                color: {TEXT_PRIMARY};\n            }}\n            QLabel {{\n                color: {TEXT_PRIMARY};\n                font-size: 14px;\n            }}\n            QLineEdit {{\n                background: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                border: 1px solid {ACCENT};\n                border-radius: 6px;\n                padding: 8px;\n                font-size: 14px;\n                selection-background-color: {ACCENT};\n                selection-color: #06210F;\n            }}\n            QLineEdit:focus {{\n                border: 1px solid {ACCENT_HOVER};\n            }}\n            QComboBox {{\n                background: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                border: 1px solid {ACCENT};\n                border-radius: 6px;\n                padding: 8px;\n                font-size: 14px;\n            }}\n            QComboBox:hover {{\n                border: 1px solid {ACCENT_HOVER};\n            }}\n            QComboBox QAbstractItemView {{\n                background: {BG_CARD};\n                color: {TEXT_PRIMARY};\n                selection-background-color: {ACCENT};\n                selection-color: #06210F;\n                border: 1px solid {ACCENT};\n            }}\n        '))
        self._station = QComboBox()
        for sid in db.list_station_ids():
            self._station.addItem(db.get_station_display_name(sid), sid)
        self._ip = QLineEdit()
        self._ip.setPlaceholderText('192.168.100.233 yoki 192.168.100.233:44021')
        self._mac = QLineEdit()
        self._mac.setPlaceholderText('AA:BB:CC:DD:EE:FF (Wake-on-LAN uchun)')
        self._brand = QComboBox()
        self._brand.addItems(['samsung', 'lg', 'artel', 'immer', 'tcl', 'xiaomi', 'sony', 'shivaki', 'yasin', 'premier', 'avalon', 'roison', 'vidaa', 'hisense', 'toshiba', 'rulls', 'ziffler', 'tizen', 'webos'])
        self._hdmi = QComboBox()
        self._hdmi.addItems(['HDMI 1', 'HDMI 2', 'HDMI 3', 'HDMI 4'])
        self._webos_hint = QLabel()
        self._webos_hint.setWordWrap(True)
        self._webos_hint.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;')
        self._webos_hint.hide()
        self._station.currentIndexChanged.connect(self._on_station_changed)
        self._brand.currentTextChanged.connect(self._update_webos_hint)
        form = QFormLayout()
        form.addRow('Stol:', self._station)
        form.addRow('TV IP / ADB port:', self._ip)
        form.addRow('TV MAC:', self._mac)
        form.addRow('Brend:', self._brand)
        form.addRow('PS ulangan HDMI:', self._hdmi)
        form.addRow('', self._webos_hint)
        save = QPushButton('💾 SAQLASH')
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setMinimumHeight(44)
        save.setStyleSheet(f'\n            QPushButton {{\n                background: {ACCENT};\n                color: #06210F;\n                font-weight: bold;\n                font-size: 15px;\n                border: none;\n                border-radius: 8px;\n                padding: 12px 20px;\n            }}\n            QPushButton:hover {{\n                background: {ACCENT_HOVER};\n            }}\n        ')
        save.clicked.connect(self._save)
        pair_btn = QPushButton('VIDAA PIN pairing…')
        pair_btn.setMinimumHeight(40)
        pair_btn.setToolTip('Faqat Hisense/Toshiba VIDAA — alohida, dastur qotmaydi')
        pair_btn.clicked.connect(self._pair_vidaa_optional)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        lay.addLayout(form)
        lay.addStretch()
        row = QHBoxLayout()
        row.addWidget(pair_btn)
        row.addWidget(save, 1)
        lay.addLayout(row)
        if self._station.count():
            self._on_station_changed()
    def _on_station_changed(self, _index: int=0) -> None:
        station_id = self._station.currentData()
        if station_id:
            self._load(str(station_id))
    def _update_webos_hint(self, brand: str='') -> None:
        """UI ipida ares/TV chaqirmaydi — qotmaslik uchun."""
        b = (brand or self._brand.currentText() or '').strip().lower()
        if b in ['lg', 'webos']:
            self._mac.setPlaceholderText('Ixtiyoriy (webOS MAC orqali boshqarilmaydi)')
            self._webos_hint.setText('LG webOS: brend «lg», IP majburiy. Avval webos_tv_ornat.bat bilan TV ga ilova o\'rnating; TV da PC IP ni kiriting.')
            self._webos_hint.show()
        else:
            if b in ['vidaa', 'hisense', 'hisense_vidaa', 'toshiba', 'toshiba_vidaa', 'tos']:
                self._mac.setPlaceholderText('Majburiy: AA:BB:CC:DD:EE:FF (VIDAA Wake-on-LAN)')
                self._webos_hint.setText('VIDAA/Toshiba: STOP TV ni o\'chiradi, START Wake-on-LAN bilan yoqadi va HDMI ga o\'tadi. Pairing bir marta + har 30 kunda (yoki TV ulanmasa) «VIDAA PIN pairing». Token ~7 kunda yangilanadi — dastur o\'zi yangilaydi.')
                self._webos_hint.show()
            elif b in ['artel', 'immer', 'tcl', 'xiaomi', 'sony', 'shivaki', 'yasin', 'premier', 'avalon', 'roison', 'rulls', 'ziffler', 'changhong']:
                self._mac.setPlaceholderText('Ixtiyoriy (faqat START da o\'chiq TV ni yoqish uchun)')
                self._webos_hint.setText(
                    'Android TV: avval android_ulash.bat ni ishga tushiring (ADB + lock APK). '
                    'Keyin shu yerda stol, brend va HDMI ni SAQLANG. '
                    'STOP — RAPTOR blok + O\'zbekiston soati; START — PlayStation HDMI.'
                )
                self._webos_hint.show()
            else:
                self._mac.setPlaceholderText('AA:BB:CC:DD:EE:FF (Wake-on-LAN uchun)')
                self._webos_hint.hide()
    def _load(self, station_id: str) -> None:
        r = db.get_tv_settings(station_id)
        self._ip.setText(r.tv_ip)
        self._mac.setText(r.tv_mac)
        idx = self._brand.findText(r.brand)
        if idx >= 0:
            self._brand.setCurrentIndex(idx)
        self._hdmi.setCurrentIndex(max(0, min(3, r.hdmi_input - 1)))
        self._update_webos_hint(r.brand)
    def _save(self) -> None:
        try:
            self._save_impl()
        except Exception as e:
            logger.exception('TV sozlamalarini saqlashda xatolik')
            QMessageBox.critical(self, 'Xatolik', f'Saqlashda xatolik:\n\n{e}')
    def _save_impl(self) -> None:
        sid = self._station.currentData() or self._station.currentText()
        if not sid:
            QMessageBox.warning(self, 'Tanlov', 'Stolni tanlang.')
            return
        else:
            sid = str(sid)
            ip_raw = self._ip.text().strip()
            brand = self._brand.currentText().strip().lower()
            hdmi_input = self._hdmi.currentIndex() + 1
            mac_raw = self._mac.text().strip()
            if ip_raw:
                host = ip_raw.rsplit(':', 1)[0] if ip_raw.count(':') == 1 and ip_raw.rsplit(':', 1)[1].isdigit() else ip_raw
                if not re.match('^\\d{1,3}(\\.\\d{1,3}){3}$', host):
                    QMessageBox.warning(self, 'IP xato', 'TV IP noto\'g\'ri ko\'rinadi.\nMisol: 192.168.1.100 yoki 192.168.1.100:5555')
                    return
                else:
                    octets = [int(x) for x in host.split('.')]
                    if any((o < 0 or o > 255 for o in octets)):
                        QMessageBox.warning(self, 'IP xato', 'Har bir raqam 0–255 oralig\'ida bo\'lishi kerak.')
                        return
                    else:
                        if host.startswith('2.168.') or host.startswith('92.168.'):
                            QMessageBox.warning(self, 'IP xato', f'\'{host}\' ehtimol noto\'g\'ri — \'192.168...\' deb boshlanishi kerak emasmi?')
                            return
                        else:
                            dup_sid = db.find_station_with_tv_ip(ip_raw, exclude_station_id=str(sid))
                            if dup_sid:
                                dup_name = db.get_station_display_name(dup_sid)
                                QMessageBox.warning(self, 'IP band', f'Bu TV IP allaqachon boshqa stolda ishlatilgan:\n\n  {dup_name} ({dup_sid})\n\nHar bir TV uchun alohida IP bo\'lishi kerak.')
                                return
            if brand in ['vidaa', 'hisense', 'hisense_vidaa', 'toshiba', 'toshiba_vidaa', 'tos'] and ip_raw and (not mac_raw):
                QMessageBox.warning(self, 'MAC kerak', 'VIDAA START bilan TV yoqilishi uchun TV MAC manzili majburiy.')
                return
            else:
                db.set_tv_settings(sid, ip_raw, mac_raw, self._brand.currentText(), hdmi_input)
                if brand in ['artel', 'immer', 'tcl', 'xiaomi', 'sony', 'shivaki', 'yasin', 'premier', 'avalon', 'roison', 'rulls', 'ziffler', 'changhong'] and ip_raw:
                    def _install_android_lock() -> None:
                        try:
                            from app.tv import tv_handler
                            host, port = tv_handler._parse_tv_host_port(ip_raw)
                            ok = tv_handler.provision_android_lock_tv(host, port, force_install=False)
                            print(f'[TVSettings] Android lock install {host}:{port} ok={ok}')
                        except Exception as e:
                            logger.warning('Android lock o\'rnatish %s: %s', sid, e)
                    threading.Thread(target=_install_android_lock, daemon=True, name=f'android-lock-{sid}').start()
                if brand in ['lg', 'webos'] and ip_raw:
                        def _push_webos() -> None:
                            try:
                                from app.tv import tv_handler, tv_platforms
                                host = tv_handler.normalize_tv_host(ip_raw)
                                tv_platforms.clear_ares_device_cache(host)
                                live = tv_platforms.sync_webos_device_mappings_from_ares()
                                if host in live:
                                    tv_platforms.register_webos_device_mapping(host, live[host])
                                pc_ip = tv_handler._get_local_ip()
                                gate_url = tv_handler._gate_url_for_host(host)
                                tv_platforms.webos_push_station_config(host, pc_ip=pc_ip, gate_url=gate_url, hdmi_input=hdmi_input, action='lock')
                            except Exception as e:
                                logger.warning('webOS sozlash %s: %s', sid, e)
                        threading.Thread(target=_push_webos, daemon=True, name=f'webos-cfg-{sid}').start()
                QMessageBox.information(self, 'OK', 'Saqlandi.\n\nAndroid TV: dastur fonida ControlPS Lock APK o\'rnatiladi (TV yoqilgan va ADB ochiq bo\'lsin).\nVIDAA uchun PIN pairing kerak bo\'lsa — «VIDAA PIN pairing» tugmasini bosing.')
    def _pair_vidaa_optional(self) -> None:
        """Pairing fon oqimida — asosiy oynani qotirmaydi."""
        brand = self._brand.currentText().strip().lower()
        if brand not in ['vidaa', 'hisense', 'hisense_vidaa', 'toshiba', 'toshiba_vidaa', 'tos']:
            QMessageBox.information(self, 'Pairing', 'Bu brend uchun VIDAA pairing kerak emas (faqat Hisense/Toshiba VIDAA).')
            return
        else:
            ip_raw = self._ip.text().strip()
            mac = self._mac.text().strip()
            if not ip_raw or not mac:
                QMessageBox.warning(self, 'Pairing', 'Avval IP va MAC ni yozib SAQLASH qiling.')
                return
            else:
                if getattr(self, '_pair_busy', False):
                    return
                else:
                    host = ip_raw.rsplit(':', 1)[0] if ip_raw.count(':') == 1 and ip_raw.rsplit(':', 1)[1].isdigit() else ip_raw
                    sid = self._station.currentData() or self._station.currentText()
                    if sid:
                        db.set_tv_settings(str(sid), ip_raw, mac, self._brand.currentText(), self._hdmi.currentIndex() + 1)
                    def _pin_provider() -> str:
                        """Fon oqimidan chaqiriladi: signal → UI da QInputDialog → javobni kutish."""
                        self._pin_event.clear()
                        self._pin_value = ''
                        self._pin_requested.emit()
                        if not self._pin_event.wait(timeout=180):
                            return ''
                        else:
                            return self._pin_value
                    self._pair_busy = True
                    def _run() -> None:
                        ok = False
                        err = ''
                        try:
                            from app.tv import vidaa_platform
                            ok = bool(vidaa_platform.pair(host, mac, _pin_provider, brand))
                        except Exception as e:
                            err = str(e)
                            logger.warning('VIDAA pairing: %s', e)
                        self._pair_done.emit(ok, err)
                    threading.Thread(target=_run, daemon=True, name=f'vidaa-pair-{host}').start()
                    QMessageBox.information(self, 'VIDAA pairing', 'TV ekraniga qarang — PIN kod chiqadi.\nBir necha soniyadan keyin shu yerda PIN kiritish oynasi ochiladi.')
    def _on_pin_requested(self) -> None:
        """UI oqimida PIN so\'rash (fon oqimidan signal orqali keladi)."""
        pin, ok = QInputDialog.getText(self, 'VIDAA PIN', 'TV ekranidagi 4 xonali PIN ni kiriting:')
        self._pin_value = (pin or '').strip() if ok else ''
        self._pin_event.set()
    def _on_pair_done(self, ok: bool, err: str) -> None:
        self._pair_busy = False
        if err:
            QMessageBox.warning(self, 'VIDAA', f'Pairing xato: {err}')
        else:
            if ok:
                QMessageBox.information(self, 'VIDAA', 'Pairing tayyor. START/STOP ishlaydi.')
            else:
                QMessageBox.warning(self, 'VIDAA', 'Pairing yakunlanmadi. TV Home ekranida bo\'lsin, Remote control yoqilgan bo\'lsin, IP/MAC ni tekshiring.\n\nAgar avval ishlagan bo\'lsa — token eskirgan: PIN pairingni qayta qiling.')