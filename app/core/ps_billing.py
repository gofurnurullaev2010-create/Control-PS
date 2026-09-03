"""PlayStation vaqt summasi — yagona ishonchli formula.\n\nQoida (hech qachon buzilmasin):\n  summa = soatlik_tarif × (soniyalar / 3600)\n\nSoniyalar:\n  VIP     → faqat START→STOP (devor soati / bazadagi start_time)\n  Vaqtli  → max(bron_qilingan, START→STOP)\n\nTarif:\n  seans BOSHLANGANDA qulflangan billing_rate (bazada).\n  Yo\'q bo\'lsa — start_time dagi stol tarifi.\n"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
_MAX_HOURLY = 100000.0
def sanitize_hourly_rate(rate: Any, fallback: float=0.0) -> float:
    try:
        r = float(rate or 0)
    except (TypeError, ValueError):
        r = 0.0
    if r < 0:
        r = 0.0
    fb = max(0.0, float(fallback or 0))
    if r > _MAX_HOURLY:
        scaled = r / 10.0
        if 1000 <= scaled <= _MAX_HOURLY:
            r = scaled
        else:
            r = fb
    return r
def parse_session_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return
    else:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        else:
            text = str(value).strip()
            if not text:
                return None
            try:
                dt = datetime.fromisoformat(text.replace('Z', ''))
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except Exception:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        return datetime.strptime(text[:19], fmt)
                    except Exception:
                        continue
                return None
def wall_seconds(start: Optional[datetime], end: Optional[datetime]) -> int:
    """START→END soniyalari (manfiy bo\'lmasin)."""
    if start is None or end is None:
        return 0
    else:
        try:
            return max(0, int((end - start).total_seconds()))
        except Exception:
            return 0
def billable_seconds(*, is_vip: bool, start: Optional[datetime], end: Optional[datetime], booked_seconds: int=0) -> int:
    """Hisob uchun soniyalar — taymerga ISHONILMAYDI."""
    wall = wall_seconds(start, end)
    if is_vip:
        return wall
    else:
        return max(int(booked_seconds or 0), wall)
def time_amount(hourly_rate: float, seconds: int) -> float:
    """Asosiy formula: tarif × soat."""
    rate = sanitize_hourly_rate(hourly_rate, 0.0)
    sec = max(0, int(seconds or 0))
    if rate <= 0 or sec <= 0:
        return 0.0
    else:
        return float(rate) * (sec / 3600.0)
def resolve_billing_rate(station_id: str, start: Optional[datetime]=None, locked_rate: Optional[float]=None) -> float:
    """Seans tarifi: avval qulflangan, keyin start vaqtidagi slot."""
    if locked_rate is not None and float(locked_rate or 0) > 0:
        return sanitize_hourly_rate(locked_rate, 0.0)
    else:
        try:
            import database as db
            fallback = sanitize_hourly_rate(db.get_station_price(station_id) or 0, 0.0)
            if start is not None:
                return sanitize_hourly_rate(db.get_station_rate_at(station_id, start), fallback)
            else:
                return fallback
        except Exception:
            return sanitize_hourly_rate(locked_rate, 0.0)
def playstation_amount(station_id: str, *, is_vip: bool, start: Optional[datetime], end: Optional[datetime], booked_seconds: int=0, locked_rate: Optional[float]=None) -> float:
    """Yagona PS summasi hisobi (STOP / live / monitor)."""
    seconds = billable_seconds(is_vip=is_vip, start=start, end=end, booked_seconds=booked_seconds)
    rate = resolve_billing_rate(station_id, start, locked_rate)
    return time_amount(rate, seconds)
def live_playstation_amount(station_id: str, *, is_vip: bool, start: Optional[datetime], now: Optional[datetime], booked_seconds: int=0, locked_rate: Optional[float]=None) -> float:
    """Jonli ekran: 0 dan o\'sadi (START→hozir). Vaqtli bron ham o\'ynagan vaqt."""
    seconds = wall_seconds(start, now)
    rate = resolve_billing_rate(station_id, start, locked_rate)
    return time_amount(rate, seconds)