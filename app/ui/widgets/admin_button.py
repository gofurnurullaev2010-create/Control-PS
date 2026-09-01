"""ADMIN tugmasi — litsenziya eslatma nuqtasi bilan."""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget
class AdminButtonWidget(QWidget):
    """ADMIN tugmasi — 1 kun qolganda qizil eslatma nuqtasi."""
    clicked = pyqtSignal()
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._btn = QPushButton('ADMIN', self)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self.clicked.emit)
        self._badge = QLabel(self)
        self._badge.setFixedSize(14, 14)
        self._badge.setStyleSheet('background-color: #111111; border-radius: 7px; border: 2px solid #FFFFFF;')
        self._badge.hide()
        sh = self._btn.sizeHint()
        self.setMinimumSize(sh)
        self.resize(sh)
        self._position_badge()
    def _position_badge(self) -> None:
        self._badge.move(max(0, self._btn.width() - 10), 2)
        self._badge.raise_()
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._btn.setGeometry(0, 0, self.width(), self.height())
        self._position_badge()
    def sizeHint(self) -> QSize:
        return self._btn.sizeHint()
    def set_badge(self, visible: bool) -> None:
        self._badge.setVisible(visible)
        if visible:
            self._position_badge()
_AdminButtonWidget = AdminButtonWidget