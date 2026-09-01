"""Kassa parqi — yopilgan kassalar ro\'yxati."""
from __future__ import annotations
from typing import Any, List
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
import database as db
def _fmt(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
class CashDiffPage(QWidget):
    """Har kungi yopilgan kassa farqlari."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 8)
        title = QLabel('Kassa parqi — yopilgan kassalar')
        title.setStyleSheet('font-size: 15px; font-weight: 800; color: #202124;')
        lay.addWidget(title)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['Sana', 'Operator', 'Kassa parqi'])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet('\n            QTableWidget { background: #FFFFFF; border: 1px solid #E8EAED; border-radius: 12px; }\n            QHeaderView::section {\n                background: #FFFFFF; color: #5F6368; padding: 10px 8px; border: none;\n                border-bottom: 1px solid #E8EAED; font-weight: 800;\n            }\n            ')
        lay.addWidget(self.table, 1)
        self.reload()
    def apply_search(self, text: str) -> None:
        q = (text or '').strip().lower()
        for row in range(self.table.rowCount()):
            hay = ' '.join((self.table.item(row, c).text().lower() if self.table.item(row, c) else '' for c in range(self.table.columnCount())))
            self.table.setRowHidden(row, bool(q and q not in hay))
    def reload(self) -> None:
        self._rows = db.list_cash_closes()
        self.table.setRowCount(len(self._rows))
        self.table.verticalHeader().setDefaultSectionSize(48)
        for i, r in enumerate(self._rows):
            day = str(r.get('business_day') or '')
            name = str(r.get('operator_name') or '').strip() or '—'
            slot = int(r.get('operator_index') or 0)
            op_label = f'{name} ({slot}-operator)' if slot else name
            diff = float(r.get('cash_diff') or 0)
            self.table.setItem(i, 0, QTableWidgetItem(day))
            self.table.setItem(i, 1, QTableWidgetItem(op_label))
            diff_item = QTableWidgetItem(_fmt(diff))
            diff_item.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
            diff_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if diff > 0:
                diff_item.setForeground(QColor('#16A34A'))
            else:
                if diff < 0:
                    diff_item.setForeground(QColor('#DC2626'))
                else:
                    diff_item.setForeground(QColor('#202124'))
            self.table.setItem(i, 2, diff_item)