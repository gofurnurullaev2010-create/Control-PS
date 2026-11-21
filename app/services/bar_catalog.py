"""BAR savdo: tanlangan kartochkani ro'yxatdagi aniq hajm bilan moslash."""
from __future__ import annotations
from typing import Any


def _volume_close(left: Any, right: Any) -> bool:
    try:
        return abs(float(left or 0) - float(right or 0)) < 0.001
    except (TypeError, ValueError):
        return False


def _kind_of(data: dict[str, Any]) -> str:
    kind = str(data.get('kind') or '').strip().lower()
    if kind in {'drink', 'market'}:
        return kind
    if 'id' in data and 'drink_name' not in data:
        return 'market'
    return 'drink'


def preselect_combo_index(entries: list[Any], preselect: dict[str, Any] | None) -> int:
    """Combo ichidan BAR da bosilgan mahsulotning aniq qatorini qaytaradi.

    Hajm raqami narx yoki qoldiq ichida qatnashsa ham boshqa hajm tanlanmaydi.
    Mos qator bo'lmasa -1.
    """
    if not preselect:
        return -1
    want = str(preselect.get('kind') or 'drink').strip().lower()
    if want not in {'drink', 'market'}:
        want = 'drink'
    for index, data in enumerate(entries):
        if not isinstance(data, dict):
            continue
        if _kind_of(data) != want:
            continue
        if want == 'drink':
            left = str(data.get('drink_name') or '').strip().casefold()
            right = str(preselect.get('drink_name') or '').strip().casefold()
            if left and left == right and _volume_close(data.get('volume'), preselect.get('volume')):
                return index
        else:
            product_id = int(preselect.get('id') or 0)
            if product_id > 0 and int(data.get('id') or 0) == product_id:
                return index
    return -1
