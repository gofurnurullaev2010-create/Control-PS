"""CLICK — karta/click to\'lovlari (1 hafta saqlanadi, o\'chirish tugmasi bilan)."""
from __future__ import annotations
from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
from app.ui.theme import ACCENT, ACCENT_HOVER, BORDER, COL_RED, TEXT_PRIMARY, TEXT_SECONDARY
from app.ui.widgets.money_spin import install_clear_zero_on_edit
def _fmt_money(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
def _fmt_dt(iso: str) -> str:
    text = str(iso or '')
    try:
        return datetime.fromisoformat(text).strftime('%d.%m.%Y %H:%M:%S')
    except ValueError:
        return text.replace('T', ' ')[:19]
class ClickPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('ClickPage')
        self.setStyleSheet(f'\n            QWidget#ClickPage {{ background:#FFFFFF; }}\n            QLabel#ClickTitle {{\n                color:{TEXT_PRIMARY}; font-size:18px; font-weight:900;\n            }}\n            QLabel#ClickHint {{\n                color:{TEXT_SECONDARY}; font-size:13px; font-weight:600;\n            }}\n            QDoubleSpinBox#ClickAmount {{\n                background:#FFFFFF; color:{TEXT_PRIMARY};\n                border:2px solid {ACCENT}; border-radius:12px;\n                padding:18px 20px; font-size:28px; font-weight:800;\n                min-height:56px;\n            }}\n            QPushButton#ClickAdd {{\n                background:{ACCENT}; color:#FFF; border:none; border-radius:12px;\n                padding:18px 28px; font-size:18px; font-weight:900; min-height:56px;\n            }}\n            QPushButton#ClickAdd:hover {{ background:{ACCENT_HOVER}; }}\n            QPushButton#ClickDel {{\n                background:#FEF2F2; color:{COL_RED}; border:1px solid {COL_RED};\n                border-radius:8px; padding:6px 12px; font-weight:800;\n            }}\n            QPushButton#ClickDel:hover {{ background:{COL_RED}; color:#FFF; }}\n            QTableWidget {{\n                background:#FFF; gridline-color:{BORDER}; border:1px solid {BORDER};\n                border-radius:10px; font-size:15px;\n            }}\n            QHeaderView::section {{\n                background:#F5F6F8; color:{TEXT_PRIMARY}; padding:10px;\n                font-weight:800; border:none; border-bottom:1px solid {BORDER};\n            }}\n            ')
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        title = QLabel('CLICK')
        title.setObjectName('ClickTitle')
        root.addWidget(title)
        hint = QLabel('Faqat summa kiriting. Ro\'yxat 7 kun saqlanadi — muddati o\'tganlari avtomatik o\'chadi.')
        hint.setObjectName('ClickHint')
        root.addWidget(hint)
        add_row = QHBoxLayout()
        add_row.setSpacing(12)
        self._amount = QDoubleSpinBox()
        self._amount.setObjectName('ClickAmount')
        self._amount.setRange(0, 1000000000)
        self._amount.setDecimals(0)
        self._amount.setSingleStep(1000)
        self._amount.setGroupSeparatorShown(True)
        self._amount.setSuffix(' so\'m')
        self._amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        install_clear_zero_on_edit(self._amount)
        add_row.addWidget(self._amount, 1)
        self._btn_add = QPushButton('Qo\'shish')
        self._btn_add.setObjectName('ClickAdd')
        self._btn_add.clicked.connect(self._add)
        add_row.addWidget(self._btn_add)
        root.addLayout(add_row)
        self._total_lbl = QLabel('Davr jami: 0 so\'m')
        self._total_lbl.setStyleSheet(f'color:{ACCENT}; font-size:15px; font-weight:800;')
        root.addWidget(self._total_lbl)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(['Sana / vaqt', 'Summa', 'O\'chirish'])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        root.addWidget(self._table, 1)
        self.reload()
    def reload(self) -> None:
        rows = db.list_clicks(7)
        self._table.setRowCount(len(rows))
        total = 0.0
        for i, r in enumerate(rows):
            amt = float(r.get('amount') or 0)
            total += amt
            cid = int(r.get('id') or 0)
            self._table.setItem(i, 0, QTableWidgetItem(_fmt_dt(str(r.get('created_time') or ''))))
            item = QTableWidgetItem(f'{_fmt_money(amt)} so\'m')
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 1, item)
            btn = QPushButton('🗑 O\'chirish')
            btn.setObjectName('ClickDel')
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, click_id=cid: self._delete(click_id))
            self._table.setCellWidget(i, 2, btn)
        try:
            period_total = float(db.click_total_for_cash_period())
        except Exception:
            period_total = total
        self._total_lbl.setText(f'Kassa davri CLICK: {_fmt_money(period_total)} so\'m   ·   7 kun ichida: {_fmt_money(total)} so\'m ({len(rows)} ta)')
    def _add(self) -> None:
        amount = float(self._amount.value())
        if amount <= 0:
            QMessageBox.warning(self, 'CLICK', 'Summani kiriting.')
            self._amount.setFocus()
            return
        else:
            try:
                db.add_click(amount)
            except Exception as e:
                QMessageBox.critical(self, 'Xatolik', str(e))
                return None
            self._amount.setValue(0)
            self.reload()
            QMessageBox.information(self, 'CLICK', f'Qo\'shildi: {_fmt_money(amount)} so\'m')
    def _delete(self, click_id: int) -> None:
        if click_id <= 0:
            return
        else:
            ok = QMessageBox.question(self, 'O\'chirish', 'Bu CLICK yozuvini o\'chirasizmi?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if ok != QMessageBox.StandardButton.Yes:
                return
            else:
                try:
                    if not db.delete_click(click_id):
                        QMessageBox.warning(self, 'CLICK', 'Yozuv topilmadi.')
                except Exception as e:
                    QMessageBox.critical(self, 'Xatolik', str(e))
                    return None
                self.reload()