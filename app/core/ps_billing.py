"""PlayStation vaqt summasi — yagona ishonchli formula.\n\nQoida (hech qachon buzilmasin):\n  summa = soatlik_tarif × (soniyalar / 3600)\n\nSoniyalar (VIP va vaqtli bir xil):\n  faqat START→STOP (o'ynagan vaqt). 1 soat bron, 15 daqiqada STOP → 15 daqiqa.\n  Taymer limitti faqat avto-STOP uchun; to'lov bron soatiga yopishtirilmaydi.\n\nTarif:\n  seans BOSHLANGANDA qulflangan billing_rate (bazada).\n  Yo\'q bo\'lsa — start_time dagi stol tarifi.\n"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Optional
_MAX_HOURLY = 100000.0
SLOT_BILLING_NOTE = 'CPS_SLOT'
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
    """Hisob uchun soniyalar — faqat o'ynagan vaqt (START→STOP)."""
    _ = is_vip
    _ = booked_seconds
    return wall_seconds(start, end)
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
    """Jonli ekran: 0 dan o\'sadi (START→hozir). STOP bilan bir xil: o'ynagan vaqt."""
    seconds = wall_seconds(start, now)
    rate = resolve_billing_rate(station_id, start, locked_rate)
    return time_amount(rate, seconds)
def session_uses_slot_billing(note: Any) -> bool:
    return str(note or '').strip().upper().startswith(SLOT_BILLING_NOTE)
def _slot_matches_minute(slot: dict[str, Any], minute: int) -> bool:
    start_minute = int(slot.get('start_minute') or 0) % 1440
    end_minute = int(slot.get('end_minute') or 0) % 1440
    if start_minute == end_minute:
        return True
    if start_minute < end_minute:
        return start_minute <= minute < end_minute
    return minute >= start_minute or minute < end_minute
def load_station_rate_slots(station_id: str) -> tuple[list[dict[str, Any]], float]:
    """Stol tarif slotlari va fallback soatlik narx."""
    try:
        import database as db
        fallback = sanitize_hourly_rate(db.get_station_price(station_id) or 0, 0.0)
        raw = db.get_station_price_slots(station_id) or []
    except Exception:
        return ([], 0.0)
    slots = []
    for item in raw:
        if not item:
            continue
        row = dict(item)
        row['hourly_rate'] = sanitize_hourly_rate(float(row.get('hourly_rate') or 0), fallback)
        row['start_minute'] = int(row.get('start_minute') or 0) % 1440
        row['end_minute'] = int(row.get('end_minute') or 0) % 1440
        slots.append(row)
    return (slots, fallback)
def rate_at_datetime(slots: list[dict[str, Any]], fallback: float, at_time: datetime) -> float:
    minute = at_time.hour * 60 + at_time.minute
    for slot in slots:
        if _slot_matches_minute(slot, minute):
            return sanitize_hourly_rate(slot.get('hourly_rate'), fallback)
    return sanitize_hourly_rate(fallback, 0.0)
def seconds_until_rate_change(slots: list[dict[str, Any]], at_time: datetime) -> int:
    """Joriy tarif oxirigacha soniyalar."""
    minute = at_time.hour * 60 + at_time.minute
    now_s = minute * 60 + int(at_time.second or 0)
    current = None
    for slot in slots:
        if _slot_matches_minute(slot, minute):
            current = slot
            break
    if not current:
        return max(1, 60 - int(at_time.second or 0))
    start_m = int(current.get('start_minute') or 0) % 1440
    end_m = int(current.get('end_minute') or 0) % 1440
    if start_m == end_m:
        left = 24 * 3600 - now_s
        return max(1, left if left > 0 else 3600)
    if start_m < end_m:
        return max(1, end_m * 60 - now_s)
    if minute >= start_m:
        return max(1, (end_m + 1440) * 60 - now_s)
    return max(1, end_m * 60 - now_s)
def slot_walked_amount(start: Optional[datetime], seconds: int, slots: list[dict[str, Any]], fallback: float) -> float:
    """Tarif o\'zgarganda ham to\'g\'ri PS summasi (slot bo\'yicha)."""
    sec = max(0, int(seconds or 0))
    if start is None or sec <= 0:
        return 0.0
    fb = sanitize_hourly_rate(fallback, 0.0)
    if not slots:
        return time_amount(fb, sec)
    rates = {sanitize_hourly_rate(s.get('hourly_rate'), fb) for s in slots}
    if len(rates) == 1:
        only = next(iter(rates))
        return time_amount(only if only > 0 else fb, sec)
    end = start + timedelta(seconds=sec)
    current = start
    total = 0.0
    guard = 0
    while current < end and guard < 20000:
        guard += 1
        rate = rate_at_datetime(slots, fb, current)
        horizon = seconds_until_rate_change(slots, current)
        seg_end = min(end, current + timedelta(seconds=horizon))
        total += float(rate) * ((seg_end - current).total_seconds() / 3600.0)
        current = seg_end
    return float(total)
def prepaid_seconds_for_amount(amount: float, start: Optional[datetime], slots: list[dict[str, Any]], fallback: float, *, max_seconds: int=7 * 24 * 3600) -> int:
    """Berilgan summaga qancha o\'yin vaqti to\'g\'ri kelishini hisoblaydi.\n\n    Masalan 17:00, 15000/soat → 18:00, keyin 18000; 24000 so\'m → 5400 s (1:30:00).
    """
    remaining = max(0.0, float(amount or 0))
    if remaining <= 0 or start is None:
        return 0
    fb = sanitize_hourly_rate(fallback, 0.0)
    current = start
    total = 0
    guard = 0
    limit = max(60, int(max_seconds or 0))
    while remaining > 0.0001 and total < limit and guard < 20000:
        guard += 1
        rate = rate_at_datetime(slots, fb, current) if slots else fb
        if rate <= 0:
            break
        if slots:
            horizon = min(seconds_until_rate_change(slots, current), limit - total)
        else:
            horizon = limit - total
        if horizon <= 0:
            break
        cost_per_sec = float(rate) / 3600.0
        afford_sec = remaining / cost_per_sec
        if afford_sec + 1e-6 >= horizon:
            take = int(horizon)
            remaining -= float(rate) * take / 3600.0
            if remaining < 0:
                remaining = 0.0
        else:
            take = int(afford_sec + 1e-6)
            remaining = 0.0
        if take <= 0:
            break
        total += take
        current = current + timedelta(seconds=take)
    return int(total)
def prepaid_seconds_for_station(station_id: str, amount: float, start: Optional[datetime]=None) -> int:
    at = start or datetime.now()
    slots, fallback = load_station_rate_slots(station_id)
    return prepaid_seconds_for_amount(amount, at, slots, fallback)
def slot_playstation_amount(station_id: str, *, start: Optional[datetime], seconds: int) -> float:
    slots, fallback = load_station_rate_slots(station_id)
    return slot_walked_amount(start, seconds, slots, fallback)