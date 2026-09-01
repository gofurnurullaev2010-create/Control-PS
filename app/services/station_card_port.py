"""StationCard uchun ma\'lumot porti — service yoki legacy db."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional, Protocol
import database as db
class StationCardPort(Protocol):
    def display_name(self, station_id: str) -> str:
        return
    def tv_settings(self, station_id: str):
        return
    def set_tv_volume(self, station_id: str, volume: int) -> None:
        return
    def drink_total(self, station_id: str, session_id: Optional[int]) -> float:
        return
    def end_session(self, session_id: int, minutes: int, revenue: float) -> None:
        return
    def transfer_session(self, session_id: int, new_station_id: str) -> bool:
        return
    def active_session(self, station_id: str) -> Optional[dict[str, Any]]:
        return
    def count_joystick_charges(self, session_id: Optional[int]) -> int:
        return
    def update_session_total_seconds(self, session_id: int, total_seconds: int) -> None:
        return
    def time_revenue(self, station_id: str, start_time: Optional[datetime], elapsed_seconds: int, *, lock_rate_at_start: bool=False) -> float:
        return
    def start_session(self, station_id: str, total_seconds: int=0, is_vip: bool=False) -> int:
        return
    def joystick_price(self) -> float:
        return
    def add_joystick_charge(self, station_id: str, price: float, session_id: Optional[int]) -> None:
        return
    def finalize_joystick_charges(self, session_id: Optional[int], end_time=None) -> float:
        return
    def session_orders_grouped(self, session_id: Optional[int], station_id: str):
        return
class LegacyStationCardPort:
    """To\'g\'ridan-to\'g\'ri database.py — legacy MainWindow uchun."""
    def display_name(self, station_id: str) -> str:
        return db.get_station_display_name(station_id)
    def tv_settings(self, station_id: str):
        return db.get_tv_settings(station_id)
    def set_tv_volume(self, station_id: str, volume: int) -> None:
        db.set_tv_volume(station_id, volume)
    def drink_total(self, station_id: str, session_id: Optional[int]) -> float:
        return float(db.get_station_drink_total(station_id, session_id))
    def end_session(self, session_id: int, minutes: int, revenue: float) -> None:
        db.end_session_row(session_id, minutes, revenue)
    def transfer_session(self, session_id: int, new_station_id: str) -> bool:
        return bool(db.transfer_active_session(session_id, new_station_id))
    def active_session(self, station_id: str) -> Optional[dict[str, Any]]:
        return db.active_session_for_station(station_id)
    def count_joystick_charges(self, session_id: Optional[int]) -> int:
        return int(db.count_joystick_charges(session_id))
    def update_session_total_seconds(self, session_id: int, total_seconds: int) -> None:
        db.update_session_total_seconds(session_id, total_seconds)
    def time_revenue(self, station_id: str, start_time: Optional[datetime], elapsed_seconds: int, *, lock_rate_at_start: bool=False) -> float:
        return float(db.calculate_station_time_revenue(station_id, start_time, elapsed_seconds, lock_rate_at_start=lock_rate_at_start))
    def start_session(self, station_id: str, total_seconds: int=0, is_vip: bool=False) -> int:
        return int(db.start_session_row(station_id, total_seconds, is_vip))
    def joystick_price(self) -> float:
        return float(db.get_joystick_price())
    def add_joystick_charge(self, station_id: str, price: float, session_id: Optional[int]) -> None:
        db.add_joystick_charge(station_id, price, session_id)
    def finalize_joystick_charges(self, session_id: Optional[int], end_time=None) -> float:
        return float(db.finalize_joystick_charges(session_id, end_time))
    def session_orders_grouped(self, session_id: Optional[int], station_id: str):
        return db.get_session_orders_grouped(session_id, station_id)
class ServiceStationCardPort:
    """AppContainer service qatlami orqali."""
    def __init__(self, container) -> None:
        self._c = container
    def display_name(self, station_id: str) -> str:
        return self._c.stations.display_name(station_id)
    def tv_settings(self, station_id: str):
        return self._c.stations.tv_settings(station_id)
    def set_tv_volume(self, station_id: str, volume: int) -> None:
        self._c.stations.set_volume(station_id, volume)
    def drink_total(self, station_id: str, session_id: Optional[int]) -> float:
        return self._c.sessions.drink_total(station_id, session_id)
    def end_session(self, session_id: int, minutes: int, revenue: float) -> None:
        self._c.sessions.end(session_id, minutes, revenue)
    def transfer_session(self, session_id: int, new_station_id: str) -> bool:
        return self._c.sessions.transfer(session_id, new_station_id)
    def active_session(self, station_id: str) -> Optional[dict[str, Any]]:
        return self._c.sessions.active_session(station_id)
    def count_joystick_charges(self, session_id: Optional[int]) -> int:
        return self._c.sessions.count_joystick_charges(session_id)
    def update_session_total_seconds(self, session_id: int, total_seconds: int) -> None:
        self._c.sessions.update_total_seconds(session_id, total_seconds)
    def time_revenue(self, station_id: str, start_time: Optional[datetime], elapsed_seconds: int, *, lock_rate_at_start: bool=False) -> float:
        return self._c.sessions.time_revenue(station_id, elapsed_seconds, start_time, lock_rate_at_start=lock_rate_at_start)
    def start_session(self, station_id: str, total_seconds: int=0, is_vip: bool=False) -> int:
        return self._c.sessions.start(station_id, total_seconds, is_vip)
    def joystick_price(self) -> float:
        return self._c.sessions.joystick_price()
    def add_joystick_charge(self, station_id: str, price: float, session_id: Optional[int]) -> None:
        self._c.sessions.add_joystick_charge(station_id, price, session_id)
    def finalize_joystick_charges(self, session_id: Optional[int], end_time=None) -> float:
        return float(self._c.sessions.finalize_joystick_charges(session_id, end_time))
    def session_orders_grouped(self, session_id: Optional[int], station_id: str):
        return self._c.sessions.orders_grouped(session_id, station_id)
def make_station_card_port(container=None) -> StationCardPort:
    if container is not None:
        return ServiceStationCardPort(container)
    else:
        return LegacyStationCardPort()