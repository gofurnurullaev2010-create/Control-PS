from __future__ import annotations
import logging
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QStringListModel
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QAbstractItemView, QComboBox, QCompleter, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
import database as db
from app.ui.dialogs.colors import ACCENT, ACCENT_HOVER, BG_CARD, BG_HEADER, BG_MAIN, BORDER_COLOR, COL_BLUE, COL_GREEN, COL_RED, GOLD_COLOR, STATUS_FREE, TEXT_PRIMARY, TEXT_SECONDARY
logger = logging.getLogger(__name__)
EXPENSE_KIND_SALARY = 'salary'
EXPENSE_KIND_RASUL = 'rasul'
EXPENSE_KIND_ABET = 'abet'
EXPENSE_KIND_AJAPA = 'ajapa'
EXPENSE_KIND_CUSTOM = 'custom'
EXPENSE_LABEL_SALARY = 'Jumishshi aylig\'i'
EXPENSE_LABEL_RASUL = 'Rasul'
EXPENSE_LABEL_ABET = 'Abet'
EXPENSE_LABEL_AJAPA = 'Ajapa'
EXPENSE_LABEL_CUSTOM = '+ Boshqa...'
class ExpenseAddDialog(QDialog):
    """Qa\'rejet kiritıw — turi Pul deregi kabi tanlanadi."""
    def __init__(self, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Qa\'rejet kiritıw')
        self.setMinimumWidth(420)
        self._resolved_type = ''
        form = QFormLayout(self)
        self.etype = QComboBox()
        self.etype.addItem(EXPENSE_LABEL_SALARY, EXPENSE_KIND_SALARY)
        self.etype.addItem(EXPENSE_LABEL_RASUL, EXPENSE_KIND_RASUL)
        self.etype.addItem(EXPENSE_LABEL_ABET, EXPENSE_KIND_ABET)
        self.etype.addItem(EXPENSE_LABEL_AJAPA, EXPENSE_KIND_AJAPA)
        self.etype.addItem(EXPENSE_LABEL_CUSTOM, EXPENSE_KIND_CUSTOM)
        self.worker_name = QLineEdit()
        self.worker_name.setPlaceholderText('Jumishshi ismi')
        self._worker_model = QStringListModel(db.list_expense_worker_names())
        worker_completer = QCompleter(self._worker_model, self)
        worker_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        worker_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        worker_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.worker_name.setCompleter(worker_completer)
        self.custom_type = QLineEdit()
        self.custom_type.setPlaceholderText('Qa\'rejet turi atı')
        self._custom_model = QStringListModel(db.list_expense_custom_types())
        custom_completer = QCompleter(self._custom_model, self)
        custom_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        custom_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        custom_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.custom_type.setCompleter(custom_completer)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 1000000000)
        self.amount.setDecimals(0)
        try:
            from app.ui.widgets.money_spin import install_clear_zero_on_edit
            install_clear_zero_on_edit(self.amount)
        except Exception:
            pass
        self.wallet = QComboBox()
        self.wallet.addItem('Kassa puli', 'cash')
        self.wallet.addItem('Ceyf puli', 'safe')
        self.note = QLineEdit()
        form.addRow('Qa\'rejet turi:', self.etype)
        self._worker_row = QWidget()
        worker_lay = QHBoxLayout(self._worker_row)
        worker_lay.setContentsMargins(0, 0, 0, 0)
        worker_lay.addWidget(self.worker_name)
        form.addRow('Ismi:', self._worker_row)
        self._custom_row = QWidget()
        custom_lay = QHBoxLayout(self._custom_row)
        custom_lay.setContentsMargins(0, 0, 0, 0)
        custom_lay.addWidget(self.custom_type)
        form.addRow('Atı:', self._custom_row)
        form.addRow('Summa:', self.amount)
        form.addRow('Pul deregi:', self.wallet)
        form.addRow('Sipatlama:', self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_btn is not None:
            save_btn.setText('Saqlaw')
        if cancel_btn is not None:
            cancel_btn.setText('Biykar etıw')
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.etype.currentIndexChanged.connect(self._sync_extra_fields)
        self._sync_extra_fields()
    def _sync_extra_fields(self) -> None:
        kind = str(self.etype.currentData() or '')
        is_salary = kind == EXPENSE_KIND_SALARY
        is_custom = kind == EXPENSE_KIND_CUSTOM
        self._worker_row.setVisible(is_salary)
        self._custom_row.setVisible(is_custom)
        form = self.layout()
        if isinstance(form, QFormLayout):
            for row_widget, show in [(self._worker_row, is_salary), (self._custom_row, is_custom)]:
                label = form.labelForField(row_widget)
                if label is not None:
                    label.setVisible(show)
        if is_salary:
            self.worker_name.setFocus()
        else:
            if is_custom:
                self.custom_type.setFocus()
    def _on_save(self) -> None:
        kind = str(self.etype.currentData() or '')
        if kind == EXPENSE_KIND_SALARY:
            name = self.worker_name.text().strip()
            if not name:
                QMessageBox.warning(self, 'Diqqat', 'Jumishshi ismin kiritin\'.')
                self.worker_name.setFocus()
                return
            else:
                self._resolved_type = f'{EXPENSE_LABEL_SALARY} — {name}'
                db.remember_expense_worker_name(name)
        else:
            if kind == EXPENSE_KIND_RASUL:
                self._resolved_type = EXPENSE_LABEL_RASUL
            else:
                if kind == EXPENSE_KIND_ABET:
                    self._resolved_type = EXPENSE_LABEL_ABET
                else:
                    if kind == EXPENSE_KIND_AJAPA:
                        self._resolved_type = EXPENSE_LABEL_AJAPA
                    else:
                        if kind == EXPENSE_KIND_CUSTOM:
                            custom = self.custom_type.text().strip()
                            if not custom:
                                QMessageBox.warning(self, 'Diqqat', 'Qa\'rejet turi atın kiritin\'.')
                                self.custom_type.setFocus()
                                return
                            else:
                                self._resolved_type = custom
                                db.remember_expense_custom_type(custom)
                        else:
                            QMessageBox.warning(self, 'Diqqat', 'Qa\'rejet turın tanlan\'.')
                            return
        if float(self.amount.value()) <= 0:
            QMessageBox.warning(self, 'Diqqat', 'Summa 0 dan katta bolsın.')
            self.amount.setFocus()
            return
        else:
            self.accept()
    def values(self) -> tuple[str, float, str, str]:
        return (self._resolved_type, float(self.amount.value()), str(self.wallet.currentData() or 'cash'), self.note.text().strip())
class PriceDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Soatbay narx')
        self._spin = QDoubleSpinBox()
        self._spin.setRange(0, 1000000000)
        self._spin.setDecimals(0)
        self._spin.setValue(db.get_hourly_rate())
        form = QFormLayout()
        form.addRow('Soatbay narx (so\'m yoki birlik):', self._spin)
        btn = QPushButton('Saqlash')
        btn.clicked.connect(self._save)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btn)
    def _save(self) -> None:
        db.set_hourly_rate(float(self._spin.value()))
        self.accept()
class ReportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Bugungi daromad')
        self.resize(520, 400)
        self.head = QLabel()
        self.head.setTextFormat(Qt.TextFormat.RichText)
        self.btn_refresh = QPushButton('🔄 YANGILASH')
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f'background-color: {ACCENT}; color: #000; font-weight: bold; padding: 8px;')
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(['Stol', 'Boshlanish', 'Tugash', 'Daqiqa', 'Tushum'])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        top_lay = QHBoxLayout()
        top_lay.addWidget(self.head)
        top_lay.addStretch()
        top_lay.addWidget(self.btn_refresh)
        lay = QVBoxLayout(self)
        lay.addLayout(top_lay)
        lay.addWidget(self.tbl)
        self.refresh_data()
    def refresh_data(self) -> None:
        total = db.today_revenue_total()
        self.head.setText(f'Bugungi daromad (yakunlangan): <b>{total:,.0f} so\'m</b>')
        rows = db.today_sessions_summary()
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.tbl.setItem(i, 0, QTableWidgetItem(db.get_station_display_name(str(r['station_id']))))
            s_t = r['start_time'].split('T')[(-1)][:5] if 'T' in (r['start_time'] or '') else r['start_time'] or ''
            e_t = r['end_time'].split('T')[(-1)][:5] if 'T' in (r['end_time'] or '') else r['end_time'] or ''
            self.tbl.setItem(i, 1, QTableWidgetItem(s_t))
            self.tbl.setItem(i, 2, QTableWidgetItem(e_t))
            self.tbl.setItem(i, 3, QTableWidgetItem(str(r['duration_minutes'] or 0)))
            rev_item = QTableWidgetItem(f"{r['revenue']:,.0f}")
            rev_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl.setItem(i, 4, rev_item)
        self.tbl.resizeRowsToContents()
class DebtorAddDialog(QDialog):
    """Yangi qarzdor qo\'shish oynasi."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Qarzdor qo\'shish')
        self.setMinimumWidth(420)
        self.setStyleSheet(f'\n            QDialog {{ background: {BG_MAIN}; color: {TEXT_PRIMARY}; }}\n            QLabel {{ color: {TEXT_PRIMARY}; font-weight: 700; }}\n            QLineEdit, QDoubleSpinBox {{\n                background: {BG_HEADER}; color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER_COLOR}; border-radius: 8px;\n                padding: 10px; font-size: 14px;\n            }}\n            QPushButton {{\n                background: {COL_GREEN}; color: #FFFFFF; font-weight: 900;\n                border: none; border-radius: 8px; padding: 10px 18px;\n            }}\n            QPushButton:hover {{ background: #22C55E; }}\n            ')
        root = QVBoxLayout(self)
        form = QFormLayout()
        from app.ui.widgets.client_suggest import ClientSuggestEdit
        self.phone = QLineEdit()
        self.phone.setPlaceholderText('Telefon raqam')
        self.name = ClientSuggestEdit(self, phone_edit=self.phone)
        self.name.setPlaceholderText('Ism yoki telefon oxirgi 4 raqam...')
        self.amount = QDoubleSpinBox()
        self.amount.setRange(1, 1000000000)
        self.amount.setDecimals(0)
        self.amount.setSingleStep(1000)
        self.note = QLineEdit()
        self.note.setPlaceholderText('Izoh (ixtiyoriy)')
        form.addRow('Klient:', self.name)
        form.addRow('Telefon:', self.phone)
        form.addRow('Qarz miqdori:', self.amount)
        form.addRow('Izoh:', self.note)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Qo\'shish')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Bekor qilish')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
    def accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, 'Ma\'lumot', 'Klient nomini kiriting.')
            return
        else:
            super().accept()
class DebtorAdjustDialog(QDialog):
    """Mavjud qarz miqdorini qo\'shish yoki kamaytirish."""
    def __init__(self, debtor: dict, parent=None) -> None:
        super().__init__(parent)
        self.debtor = debtor
        self.setWindowTitle('Qarz miqdorini o\'zgartirish')
        self.setMinimumWidth(420)
        self.setStyleSheet(f'\n            QDialog {{ background: {BG_MAIN}; color: {TEXT_PRIMARY}; }}\n            QLabel {{ color: {TEXT_PRIMARY}; font-weight: 700; }}\n            QDoubleSpinBox {{\n                background: {BG_HEADER}; color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER_COLOR}; border-radius: 8px;\n                padding: 10px; font-size: 14px;\n            }}\n            QPushButton {{\n                color: #FFFFFF; font-weight: 900;\n                border: none; border-radius: 8px; padding: 10px 18px;\n            }}\n            QPushButton#AddAmount {{ background: {COL_GREEN}; }}\n            QPushButton#SubAmount {{ background: {COL_RED}; }}\n            QPushButton#CancelAmount {{ background: {TEXT_SECONDARY}; }}\n            ')
        root = QVBoxLayout(self)
        name = str(debtor.get('client_name', ''))
        phone = str(debtor.get('phone', '') or '')
        current = float(debtor.get('amount', 0) or 0)
        title = QLabel(f"{name} {('- ' + phone if phone else '')}")
        title.setStyleSheet('font-size: 18px; font-weight: 900;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        self.current_lbl = QLabel(f'Hozirgi qarz: {current:,.0f} so\'m')
        self.current_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_lbl.setStyleSheet(f'color: {COL_RED}; font-size: 16px; font-weight: 900;')
        root.addWidget(self.current_lbl)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(1, 1000000000)
        self.amount.setDecimals(0)
        self.amount.setSingleStep(1000)
        self.amount.setValue(1000)
        root.addWidget(self.amount)
        row = QHBoxLayout()
        add = QPushButton('+ Qo\'shish')
        add.setObjectName('AddAmount')
        add.clicked.connect(lambda: self._apply(+self.amount.value()))
        sub = QPushButton('- Kamaytirish')
        sub.setObjectName('SubAmount')
        sub.clicked.connect(lambda: self._apply(-self.amount.value()))
        cancel = QPushButton('Yopish')
        cancel.setObjectName('CancelAmount')
        cancel.clicked.connect(self.reject)
        row.addWidget(add)
        row.addWidget(sub)
        row.addWidget(cancel)
        root.addLayout(row)
    def _apply(self, delta: float) -> None:
        try:
            db.adjust_debtor_amount(int(self.debtor['id']), delta)
        except Exception as e:
            QMessageBox.critical(self, 'Xatolik', str(e))
            return None
        self.accept()
class DebtorsDialog(QDialog):
    """Qarzdorlar ro\'yxati: chapda kunlar, o\'ngda qarzlar."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Qarizdorlar')
        self.resize(980, 620)
        self._selected_day = None
        self.setStyleSheet(''.join(f'\n            QDialog {{ background: {BG_MAIN}; color: {TEXT_PRIMARY}; }}\n            QLabel {{ color: {TEXT_PRIMARY}; }}\n            QLineEdit {{\n                background: {BG_HEADER}; color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER_COLOR}; border-radius: 8px;\n                padding: 9px; font-size: 14px;\n            }}\n            QPushButton {{\n                background: {BG_HEADER}; color: {BORDER_COLOR}; border-radius: 8px;\n                padding: 9px 14px; font-weight: 800;\n            }}\n            QPushButton:hover {{ border: 1px solid {ACCENT}; }}\n            QPushButton#AddDebt {{\n                background: #6B7C3B; color: #FFFFFF; border: none;\n            }}\n            QPushButton#PaidDebt {{\n                background: {COL_GREEN}; color: #FFFFFF; border: none;\n            }}\n            QListWidget, QTableWidget {{\n                background: {BG_CARD}; color: {BORDER_COLOR}; gridline-color: {BORDER_COLOR};\n            }}\n            QListWidget::item {{\n                padding: 9px; border-bottom: 1px solid {BORDER_COLOR};\n            }}\n            QListWidget::item:selected {{\n                background: #E8F2E2; color: {TEXT_PRIMARY};\n            }}\n            QHeaderView::section {{\n                background: {BG_HEADER}; color: {TEXT_PRIMARY};\n                padding: 8px; border: 1px solid {BORDER_COLOR};\n                font-weight: 900;\n            }}\n            '))
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel('Qarizdorlar')
        title.setStyleSheet('font-size: 20px; font-weight: 900;')
        top.addWidget(title)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Izlew Qarizdarlar')
        self.search.textChanged.connect(self._reload_debtors)
        top.addWidget(self.search, 1)
        add = QPushButton('+ Qo\'siw')
        add.setObjectName('AddDebt')
        add.clicked.connect(self._add_debtor)
        top.addWidget(add)
        refresh = QPushButton('⟳')
        refresh.clicked.connect(self._reload_all)
        top.addWidget(refresh)
        root.addLayout(top)
        body = QHBoxLayout()
        self.days = QListWidget()
        self.days.setFixedWidth(170)
        self.days.itemClicked.connect(self._on_day_clicked)
        body.addWidget(self.days)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Klient', 'Qariz mug\'dari', 'Qariz waqti', 'Izoh', ''])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._on_table_clicked)
        body.addWidget(self.table, 1)
        root.addLayout(body, 1)
        self._rows = []
        self._reload_all()
    def _reload_all(self) -> None:
        self._reload_days()
        self._reload_debtors()
    def _reload_days(self) -> None:
        self.days.clear()
        total_all = sum((float(r.get('total', 0) or 0) for r in db.debtor_day_summary()))
        all_item = QListWidgetItem(f'Barligi        {total_all:,.0f}')
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.days.addItem(all_item)
        for row in db.debtor_day_summary():
            day = str(row.get('day') or '')
            total = float(row.get('total', 0) or 0)
            item = QListWidgetItem(f'{day}     {total:,.0f}')
            item.setData(Qt.ItemDataRole.UserRole, day)
            self.days.addItem(item)
        self.days.setCurrentRow(0)
    def _on_day_clicked(self, item: QListWidgetItem) -> None:
        self._selected_day = item.data(Qt.ItemDataRole.UserRole)
        self._reload_debtors()
    def _reload_debtors(self) -> None:
        rows = db.list_debtors(self.search.text(), self._selected_day)
        self._rows = rows
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            name = str(r.get('client_name', ''))
            phone = str(r.get('phone', '') or '')
            if phone:
                name = f'{name} - {phone}'
            amount_item = QTableWidgetItem(f"{float(r.get('amount', 0)):,.0f}")
            amount_item.setForeground(QColor(COL_RED))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            time_text = self._fmt_dt(str(r.get('debt_time', '')))
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, amount_item)
            self.table.setItem(i, 2, QTableWidgetItem(time_text))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get('note', '') or '')))
            paid = QPushButton('✓')
            paid.setObjectName('PaidDebt')
            paid.setToolTip('To\'landi deb yopish')
            paid.clicked.connect(lambda _=False, did=int(r['id']): self._mark_paid(did))
            self.table.setCellWidget(i, 4, paid)
    def _on_table_clicked(self, row: int, col: int) -> None:
        if col != 0 or row < 0 or row >= len(self._rows):
            return None
        else:
            dlg = DebtorAdjustDialog(self._rows[row], self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._reload_all()
    def _add_debtor(self) -> None:
        dlg = DebtorAddDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        else:
            try:
                db.add_debtor(dlg.name.text(), dlg.phone.text(), dlg.amount.value(), dlg.note.text())
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
                return None
            self._selected_day = None
            self._reload_all()
    def _mark_paid(self, debtor_id: int) -> None:
        db.mark_debtor_paid(debtor_id, True)
        self._reload_all()
    @staticmethod
    def _fmt_dt(value: str) -> str:
        if 'T' in value:
            d, t = value.split('T', 1)
            return f'{d} г. {t[:8]}'
        else:
            return value