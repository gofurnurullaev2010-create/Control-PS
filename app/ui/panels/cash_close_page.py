"""Kassa jabıw sahifasi — rasmdagi forma (Operator tanlash bilan)."""
from __future__ import annotations
from datetime import datetime
from typing import Callable, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
import database as db
from app.auth import app_password
from app.ui.theme import ACCENT, ACCENT_HOVER, BORDER, COL_RED, TEXT_PRIMARY, TEXT_SECONDARY
def _fmt_money(value: float) -> str:
    return f'{float(value or 0):,.0f}'.replace(',', ' ')
def _fmt_dt(iso: str) -> str:
    text = str(iso or '')
    if 'T' in text:
        d, t = text.split('T', 1)
        try:
            dt = datetime.fromisoformat(text)
            return dt.strftime('%d.%m.%Y %H:%M:%S')
        except ValueError:
            return f'{d} {t[:8]}'
    else:
        return text[:19]
class CashClosePage(QWidget):
    """Asosiy oynadagi Kassa jabıw formasi."""
    def __init__(self, parent=None, on_cancel: Optional[Callable[[], None]]=None, on_saved: Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self._on_cancel = on_cancel
        self._on_saved = on_saved
        self._report = {}
        self._closing_touched = False
        self.setObjectName('CashClosePage')
        self.setStyleSheet(f'\n            QWidget#CashClosePage {{ background: #FFFFFF; }}\n            QLabel#SectionTitle {{\n                color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 800;\n                margin-top: 10px; margin-bottom: 4px;\n            }}\n            QLabel#FieldLabel {{\n                color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 600;\n                min-width: 200px;\n            }}\n            QLineEdit, QComboBox, QDoubleSpinBox {{\n                background: #FFFFFF; color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER}; border-radius: 8px;\n                padding: 10px 12px; font-size: 14px; min-height: 20px;\n            }}\n            QLineEdit:read-only {{ background: #F7F7F7; }}\n            QComboBox:hover, QDoubleSpinBox:focus, QLineEdit:focus {{\n                border: 1px solid {ACCENT};\n            }}\n            QPushButton#CashCancel {{\n                background: #FFFFFF; color: {TEXT_PRIMARY};\n                border: 1px solid {BORDER}; border-radius: 6px;\n                padding: 9px 18px; font-weight: 700;\n            }}\n            QPushButton#CashCancel:hover {{ background: #F5F5F5; }}\n            QPushButton#CashSave {{\n                background: {ACCENT}; color: #FFFFFF;\n                border: none; border-radius: 6px;\n                padding: 9px 22px; font-weight: 800;\n            }}\n            QPushButton#CashSave:hover {{ background: {ACCENT_HOVER}; }}\n            QLabel#CashError {{\n                color: {COL_RED}; font-size: 12px; font-weight: 700;\n            }}\n            ')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = QWidget()
        header.setObjectName('CashHeader')
        header.setStyleSheet(f'QWidget#CashHeader {{ background:#FFFFFF; border-bottom:1px solid {BORDER}; }}')
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 10, 20, 10)
        h.addStretch()
        self._btn_cancel = QPushButton('Biykar etiw')
        self._btn_cancel.setObjectName('CashCancel')
        self._btn_cancel.clicked.connect(self._cancel)
        h.addWidget(self._btn_cancel)
        self._btn_save = QPushButton('Saqlaw')
        self._btn_save.setObjectName('CashSave')
        self._btn_save.clicked.connect(self._save)
        h.addWidget(self._btn_save)
        root.addWidget(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(28, 18, 28, 28)
        body_lay.setSpacing(8)
        body_lay.addWidget(self._section('Ashılg\'an kassa mag\'lıwmati'))
        open_form = QFormLayout()
        open_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        open_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        open_form.setHorizontalSpacing(24)
        open_form.setVerticalSpacing(12)
        self._operator = QComboBox()
        self._operator.setMinimumWidth(280)
        self._operator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        open_form.addRow(self._label('Operator *'), self._operator)
        self._open_time = QLineEdit()
        self._open_time.setReadOnly(True)
        open_form.addRow(self._label('Kassa ashiw waqti'), self._open_time)
        body_lay.addLayout(open_form)
        body_lay.addWidget(self._section('Tu\'simler'))
        income_form = QFormLayout()
        income_form.setHorizontalSpacing(24)
        income_form.setVerticalSpacing(12)
        self._ps_income = self._ro_field()
        self._goods_income = self._ro_field()
        self._total_income = self._ro_field()
        income_form.addRow(self._label('Playstation tu\'simi'), self._ps_income)
        income_form.addRow(self._label('Tovarlardan tu\'sim'), self._goods_income)
        income_form.addRow(self._label('Uliwmaliq tu\'sim'), self._total_income)
        body_lay.addLayout(income_form)
        body_lay.addWidget(self._section('Kassa jabiw mag\'lıwmati'))
        close_form = QFormLayout()
        close_form.setHorizontalSpacing(24)
        close_form.setVerticalSpacing(12)
        self._expense = self._ro_field()
        self._debts = self._ro_field()
        self._debts_paid = self._ro_field()
        close_form.addRow(self._label('Uliwmaliq qa\'rejet'), self._expense)
        close_form.addRow(self._label('Qarizlar'), self._debts)
        close_form.addRow(self._label('Qarizin to\'legenler'), self._debts_paid)
        closing_wrap = QWidget()
        cw = QVBoxLayout(closing_wrap)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(4)
        closing_row = QHBoxLayout()
        closing_row.setSpacing(10)
        self._closing = QDoubleSpinBox()
        self._closing.setRange(0, 1000000000)
        self._closing.setDecimals(0)
        self._closing.setSingleStep(1000)
        self._closing.setGroupSeparatorShown(True)
        self._closing.setSuffix(' so\'m')
        self._closing.valueChanged.connect(self._on_closing_changed)
        from app.ui.widgets.money_spin import install_clear_zero_on_edit
        install_clear_zero_on_edit(self._closing)
        closing_row.addWidget(self._closing, 1)
        self._click_spin = QDoubleSpinBox()
        self._click_spin.setRange(0, 1000000000)
        self._click_spin.setDecimals(0)
        self._click_spin.setSingleStep(1000)
        self._click_spin.setGroupSeparatorShown(True)
        self._click_spin.setPrefix('+')
        self._click_spin.setSuffix(' so\'m')
        self._click_spin.setMinimumWidth(160)
        self._click_spin.setToolTip('CLICK summasi — o\'zgartirish mumkin. O\'zgarsa Kassa parqi ham yangilanadi.')
        self._click_spin.setStyleSheet(f'color:{ACCENT}; font-size:15px; font-weight:900; border:1px solid {ACCENT};')
        self._click_spin.valueChanged.connect(self._on_click_changed)
        install_clear_zero_on_edit(self._click_spin)
        closing_row.addWidget(self._click_spin)
        cw.addLayout(closing_row)
        self._closing_formula = QLabel('Jawılg\'andag\'i summa: 0+0=0')
        self._closing_formula.setStyleSheet(f'color:{TEXT_PRIMARY}; font-size:14px; font-weight:800;')
        self._closing_formula.setWordWrap(True)
        cw.addWidget(self._closing_formula)
        self._closing_err = QLabel('! Bul jazıw talap etiledi')
        self._closing_err.setObjectName('CashError')
        self._closing_err.setVisible(True)
        cw.addWidget(self._closing_err)
        close_form.addRow(self._label('Jawılg\'andag\'i summa *'), closing_wrap)
        self._cash_diff = self._ro_field()
        close_form.addRow(self._label('Kassa parqi'), self._cash_diff)
        body_lay.addLayout(close_form)
        body_lay.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.reload()
    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName('SectionTitle')
        return lbl
    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName('FieldLabel')
        return lbl
    @staticmethod
    def _ro_field() -> QLineEdit:
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setMinimumWidth(280)
        return edit
    def _load_operators(self) -> None:
        self._operator.clear()
        app_password.load_operators()
        for slot in app_password.operator_slots():
            name = db.get_operator_name(slot)
            label = name if name else f'{slot}-operator'
            if name and (not name.endswith('-operator')) and (f'{slot}-' not in name):
                        label = f'{name}'
            self._operator.addItem(label, slot)
    def reload(self) -> None:
        self._load_operators()
        self._closing_touched = False
        self._closing.blockSignals(True)
        self._closing.setValue(0)
        self._closing.blockSignals(False)
        self._closing_err.setVisible(True)
        try:
            report = db.operator_report_for_day()
        except Exception as e:
            self._report = {}
            QMessageBox.warning(self, 'Xatolik', f'Hisobot yuklanmadi:\n{e}')
            return None
        self._report = report
        goods = float(report.get('drink_total', 0) or 0) + float(report.get('market_total', 0) or 0)
        report['goods_total'] = goods
        try:
            click_total = float(db.click_total_for_cash_period())
        except Exception:
            click_total = 0.0
        report['click_total'] = click_total
        ps_income = float(report.get('session_total', 0) or 0) + float(report.get('joystick_total', 0) or 0)
        self._open_time.setText(_fmt_dt(str(report.get('period_start') or '')))
        self._ps_income.setText(_fmt_money(ps_income))
        self._goods_income.setText(_fmt_money(goods))
        self._total_income.setText(_fmt_money(float(report.get('total', 0) or 0)))
        self._expense.setText(_fmt_money(float(report.get('expense_total', 0) or 0)))
        self._debts.setText(_fmt_money(float(report.get('debt_total', 0) or 0)))
        self._debts_paid.setText(_fmt_money(float(report.get('debt_paid_total', 0) or 0)))
        self._click_spin.blockSignals(True)
        self._click_spin.setValue(float(click_total or 0))
        self._click_spin.blockSignals(False)
        self._update_cash_diff()
    def _click_total(self) -> float:
        try:
            return float(self._click_spin.value())
        except (TypeError, ValueError):
            return 0.0
    def _expected_amount(self) -> float:
        r = self._report or {}
        return float(r.get('total', 0) or 0) - float(r.get('expense_total', 0) or 0) - float(r.get('debt_total', 0) or 0) + float(r.get('debt_paid_total', 0) or 0)
    def _update_cash_diff(self) -> None:
        expected = self._expected_amount()
        cash = float(self._closing.value())
        click = self._click_total()
        total_close = cash + click
        diff = total_close - expected
        self._closing_formula.setText(f'Jawılg\'andag\'i summa: {_fmt_money(cash)}+{_fmt_money(click)}={_fmt_money(total_close)}')
        self._cash_diff.setText(_fmt_money(diff))
        if diff > 0:
            color = '#16A34A'
        else:
            if diff < 0:
                color = '#DC2626'
            else:
                color = '#202124'
        self._cash_diff.setStyleSheet(f'background:#F7F7F7; color:{color}; border:1px solid #E5E7EB; border-radius:8px; padding:10px 12px; font-size:15px; font-weight:800;')
    def _on_closing_changed(self, _value: float) -> None:
        self._closing_touched = True
        self._closing_err.setVisible(False)
        self._update_cash_diff()
    def _on_click_changed(self, _value: float) -> None:
        if self._report is not None:
            self._report['click_total'] = float(self._click_spin.value())
        self._update_cash_diff()
    def _cancel(self) -> None:
        self.reload()
        if self._on_cancel:
            self._on_cancel()
    def _save(self) -> None:
        if self._operator.count() <= 0:
            QMessageBox.warning(self, 'Operator', 'Operatorlar topilmadi.')
            return
        else:
            if not self._closing_touched:
                self._closing_err.setVisible(True)
                self._closing.setFocus()
                return
            else:
                slot = int(self._operator.currentData())
                name = self._operator.currentText().strip()
                report = dict(self._report or {})
                report['goods_total'] = float(report.get('goods_total', 0) or 0)
                closing = float(self._closing.value())
                click = self._click_total()
                report['click_total'] = click
                report['closing_amount'] = closing
                report['closing_with_click'] = closing + click
                try:
                    result = db.close_cash_register(slot, closing, operator_name=name, report=report)
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', f'Saqlashda xatolik:\n{e}')
                    return None
                total_close = closing + click
                tg_note = ''
                try:
                    from app.services.telegram_notify import get_telegram_chat_ids, get_telegram_config
                    token, _ = get_telegram_config()
                    if not token or not get_telegram_chat_ids():
                        tg_note = '\n\nTelegram sozlanmagan — hisobot yuborilmadi.'
                    else:
                        tg_note = '\n\nTelegram hisobot fonida yuborilmoqda.'
                except Exception:
                    tg_note = '\n\nTelegram holatini tekshirib bo\'lmadi.'
                QMessageBox.information(self, 'Saqlandi', f"Kassa jabıw saqlandi.\nOperator: {name}\nJawılg\'andag\'i summa: {_fmt_money(closing)} so\'m\nCLICK: {_fmt_money(click)} so\'m\nJami (naqd+CLICK): {_fmt_money(total_close)} so\'m\nKassa parqi: {_fmt_money(float(result.get('cash_diff') or 0))} so\'m\nBugungi kassa: 0{tg_note}")
                self.reload()
                if self._on_saved:
                    self._on_saved()