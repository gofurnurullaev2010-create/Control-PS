from __future__ import annotations
from typing import List
from app.db.repositories.stations import StationRepository
class StationService:
    def __init__(self, repo: StationRepository) -> None:
        self._repo = repo
    def list_station_ids(self) -> List[str]:
        return self._repo.list_station_ids()
    def display_name(self, station_id: str) -> str:
        return self._repo.get_display_name(station_id)
    def hourly_rate(self, station_id: str) -> float:
        return self._repo.get_price(station_id)
    def tv_settings(self, station_id: str):
        return self._repo.get_tv_settings(station_id)
    def set_volume(self, station_id: str, volume: int) -> None:
        self._repo.set_tv_volume(station_id, volume)
    def time_revenue(self, station_id: str, seconds: int, at_time=None) -> float:
        return self._repo.calculate_time_revenue(station_id, seconds, at_time)