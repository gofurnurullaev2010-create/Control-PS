"""QDoubleSpinBox: fokusda 0 tanlanadi — yozganda 0 qo\'shilmaydi."""
from __future__ import annotations
from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import QDoubleSpinBox
class _ClearZeroFilter(QObject):
    def eventFilter(self, obj, event) -> bool:
        if event is None:
            return False
        else:
            et = event.type()
            if et == QEvent.Type.FocusIn:
                QTimer.singleShot(0, lambda o=obj: self._select_all(o))
            else:
                if et == QEvent.Type.MouseButtonPress:
                    QTimer.singleShot(0, lambda o=obj: self._select_all(o))
            return False
    @staticmethod
    def _select_all(obj) -> None:
        try:
            if isinstance(obj, QDoubleSpinBox):
                le = obj.lineEdit()
                if le is not None:
                    le.selectAll()
                elif hasattr(obj, 'selectAll'):
                    obj.selectAll()
        except Exception:
            return None
_FILTERS: list[_ClearZeroFilter] = []
def install_clear_zero_on_edit(spin: QDoubleSpinBox) -> None:
    """Har bir summa spinboxiga ulang — \'0 so\'m\' ustiga yozganda 0 qolmasin."""
    if spin is None:
        return
    else:
        filt = _ClearZeroFilter(spin)
        spin.installEventFilter(filt)
        le = spin.lineEdit()
        if le is not None:
            le.installEventFilter(filt)
            le.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        _FILTERS.append(filt)