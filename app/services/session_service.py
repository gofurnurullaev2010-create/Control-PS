from __future__ import annotations
from typing import Any, List, Optional
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.stations import StationRepository
class SessionService:
    def __init__(self, sessions: SessionRepository, stations: StationRepository) -> None:
        self._sessions = sessions
        self._stations = stations
    def active_session(self, station_id: str) -> Optional[dict[str, Any]]:
        return self._sessions.active_for_station(station_id)
    def start(self, station_id: str, total_seconds: int=0, is_vip: bool=False) -> int:
        return self._sessions.start(station_id, total_seconds, is_vip)
    def end(self, session_id: int, duration_minutes: int, revenue: float) -> None:
        self._sessions.end(session_id, duration_minutes, revenue)
    def update_total_seconds(self, session_id: int, total_seconds: int) -> None:
        self._sessions.update_total_seconds(session_id, total_seconds)
    def transfer(self, session_id: int, new_station_id: str) -> bool:
        return self._sessions.transfer(session_id, new_station_id)
    def drink_total(self, station_id: str, session_id: Optional[int]) -> float:
        return self._sessions.drink_total(station_id, session_id)
    def time_revenue(self, station_id: str, seconds: int, at_time=None, *, lock_rate_at_start: bool=False) -> float:
        return self._stations.calculate_time_revenue(station_id, seconds, at_time, lock_rate_at_start=lock_rate_at_start)
    def daily_report(self, day: Optional[str]=None) -> List[dict[str, Any]]:
        return self._sessions.detailed_daily_report(day)
    def today_revenue(self) -> float:
        return float(self._sessions.today_revenue_total())
    def revenue_split(self, day: Optional[str]=None) -> dict[str, float]:
        biz = day or self._sessions.current_business_date().isoformat()
        return self._sessions.revenue_split_for_day(biz)
    def joystick_price(self) -> float:
        return self._sessions.joystick_price()
    def add_joystick_charge(self, station_id: str, price: float, session_id: Optional[int]=None) -> None:
        self._sessions.add_joystick_charge(station_id, price, session_id)
    def count_joystick_charges(self, session_id: Optional[int]) -> int:
        return self._sessions.count_joystick_charges(session_id)
    def finalize_joystick_charges(self, session_id: Optional[int], end_time=None) -> float:
        return self._sessions.finalize_joystick_charges(session_id, end_time)
    def orders_grouped(self, session_id: Optional[int], station_id: str):
        return self._sessions.orders_grouped(session_id, station_id)