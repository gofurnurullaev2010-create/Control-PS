from __future__ import annotations
from typing import Any, List, Optional
from app.db import legacy
class StationRepository:
    """Stollar, narxlar va TV sozlamalari."""
    def init_db(self) -> None:
        legacy.init()
    def list_station_ids(self) -> List[str]:
        return legacy.module().list_station_ids()
    def get_station_count(self) -> int:
        return legacy.module().get_station_count()
    def get_display_name(self, station_id: str) -> str:
        return legacy.module().get_station_display_name(station_id)
    def get_price(self, station_id: str) -> float:
        return float(legacy.module().get_station_price(station_id))
    def get_tv_settings(self, station_id: str):
        return legacy.module().get_tv_settings(station_id)
    def set_tv_volume(self, station_id: str, volume: int) -> None:
        legacy.module().set_tv_volume(station_id, volume)
    def get_price_slots(self, station_id: str) -> list[dict[str, Any]]:
        return legacy.module().get_station_price_slots(station_id)
    def calculate_time_revenue(self, station_id: str, seconds: int, at_time=None, *, lock_rate_at_start: bool=False) -> float:
        return float(legacy.module().calculate_station_time_revenue(station_id, at_time, seconds, lock_rate_at_start=lock_rate_at_start))