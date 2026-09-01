"""Sklad sahifasi — Foto | Tovar | Qaldiq | Keliw baxasi | Satiw baxasi."""
from __future__ import annotations
from typing import Any, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
def _fmt(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
class WarehousePage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Foto', 'Tovar ati', 'Qaldiq', 'Keliw baxasi', 'Satiw baxasi'])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 72)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet('\n            QTableWidget {\n                background: #FFFFFF; border: none; gridline-color: #F0F1F4;\n                font-size: 14px;\n            }\n            QHeaderView::section {\n                background: #FFFFFF; color: #5F6368; padding: 10px 8px;\n                border: none; border-bottom: 1px solid #E5E7EB; font-weight: 800;\n            }\n            QTableWidget::item { padding: 6px; border-bottom: 1px solid #F0F1F4; }\n            ')
        lay.addWidget(self.table)
    def set_products(self, products: List[dict[str, Any]]) -> None:
        self.table.setRowCount(len(products))
        self.table.verticalHeader().setDefaultSectionSize(64)
        for i, p in enumerate(products):
            img_lbl = QLabel()
            img_lbl.setFixedSize(56, 56)
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setStyleSheet('background: #F8FAFC; border-radius: 6px;')
            raw = p.get('image')
            if raw:
                pix = QPixmap()
                if pix.loadFromData(bytes(raw)) and (not pix.isNull()):
                    img_lbl.setPixmap(pix.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    img_lbl.setText('—')
            else:
                img_lbl.setText('—')
                img_lbl.setStyleSheet('color: #9CA3AF;')
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(4, 4, 4, 4)
            wl.addWidget(img_lbl)
            self.table.setCellWidget(i, 0, wrap)
            name_item = QTableWidgetItem(str(p.get('name') or ''))
            name_item.setFont(QFont('Segoe UI', 12, QFont.Weight.DemiBold))
            self.table.setItem(i, 1, name_item)
            qty_item = QTableWidgetItem(_fmt(float(p.get('quantity') or 0)))
            qty_item.setForeground(QColor('#16A34A'))
            qty_item.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, qty_item)
            buy_item = QTableWidgetItem(_fmt(float(p.get('purchase') or 0)))
            buy_item.setForeground(QColor('#111827'))
            buy_item.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
            buy_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 3, buy_item)
            sell_item = QTableWidgetItem(_fmt(float(p.get('price') or 0)))
            sell_item.setForeground(QColor('#DC2626'))
            sell_item.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
            sell_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 4, sell_item)
            self.table.setRowHeight(i, 64)
    def apply_search(self, text: str) -> None:
        q = (text or '').strip().lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            hay = (item.text() if item else '').lower()
            self.table.setRowHidden(row, bool(q and q not in hay))