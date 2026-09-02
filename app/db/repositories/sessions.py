from __future__ import annotations
from typing import Any, List, Optional
from app.db import legacy
class SessionRepository:
    """Seanslar va ularga bog\'liq buyurtmalar."""
    def active_for_station(self, station_id: str) -> Optional[dict[str, Any]]:
        return legacy.module().active_session_for_station(station_id)
    def start(self, station_id: str, total_seconds: int=0, is_vip: bool=False) -> int:
        return int(legacy.module().start_session_row(station_id, total_seconds, is_vip))
    def end(self, session_id: int, duration_minutes: int, revenue: float) -> None:
        legacy.module().end_session_row(session_id, duration_minutes, revenue)
    def update_total_seconds(self, session_id: int, total_seconds: int) -> None:
        legacy.module().update_session_total_seconds(session_id, total_seconds)
    def transfer(self, session_id: int, new_station_id: str) -> bool:
        return bool(legacy.module().transfer_active_session(session_id, new_station_id))
    def drink_total(self, station_id: str, session_id: Optional[int]) -> float:
        return float(legacy.module().get_station_drink_total(station_id, session_id))
    def joystick_total(self, station_id: str, session_id: Optional[int]) -> float:
        return float(legacy.module().get_session_joystick_total(station_id, session_id))
    def orders_grouped(self, session_id: Optional[int], station_id: Optional[str]=None):
        return legacy.module().get_session_orders_grouped(session_id, station_id)
    def detailed_daily_report(self, day: Optional[str]=None):
        return legacy.module().get_detailed_daily_report(day)
    def revenue_split_for_day(self, day: str) -> dict[str, float]:
        return legacy.module().revenue_split_for_day(day)
    def today_revenue_total(self) -> float:
        return float(legacy.module().today_revenue_total())
    def current_business_date(self):
        return legacy.module().current_business_date()
    def add_joystick_charge(self, station_id: str, price: float, session_id: Optional[int]=None) -> None:
        legacy.module().add_joystick_charge(station_id, price, session_id)
    def joystick_price(self) -> float:
        return float(legacy.module().get_joystick_price())
    def count_joystick_charges(self, session_id: Optional[int]) -> int:
        return int(legacy.module().count_joystick_charges(session_id))
    def finalize_joystick_charges(self, session_id: Optional[int], end_time=None) -> float:
        return float(legacy.module().finalize_joystick_charges(session_id, end_time))