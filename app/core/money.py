"""Pul summalarini yaxlitlash — hisob-kitob faqat mingliklarda."""
from __future__ import annotations
def round_to_thousand(amount: float | int | None) -> float:
    """Jami to\'lovni ming so\'mga yaxlitlash.\n\n    Qoida: qoldiq >= 500 → yuqoriga; < 500 → pastga.\n    Masalan: 12783 → 13000, 27421 → 27000.\n    """
    try:
        x = float(amount or 0)
    except (TypeError, ValueError):
        return 0.0
    if x <= 0:
        return 0.0
    else:
        return float(int((x + 500.0) // 1000.0) * 1000)
def as_thousand(amount: float | int | None) -> float:
    """Hisob-kitobga yozish uchun: har doim minglik (0 yoki ±N000)."""
    try:
        x = float(amount or 0)
    except (TypeError, ValueError):
        return 0.0
    if x == 0:
        return 0.0
    else:
        sign = 1.0 if x > 0 else (-1.0)
        return sign * round_to_thousand(abs(x))