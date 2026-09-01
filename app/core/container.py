"""Application service container — barcha modullar shu orqali bog\'lanadi."""
from __future__ import annotations
from dataclasses import dataclass
from app.db.repositories.finance import FinanceRepository
from app.db.repositories.inventory import InventoryRepository
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.stations import StationRepository
from app.services.auth_service import AuthService
from app.services.finance_service import FinanceService
from app.services.inventory_service import InventoryService
from app.services.auth_service import LicenseService
from app.services.session_service import SessionService
from app.services.station_service import StationService
from app.services.tv_service import TVService
@dataclass
class AppContainer:
    stations: StationService
    sessions: SessionService
    inventory: InventoryService
    finance: FinanceService
    auth: AuthService
    license: LicenseService
    tv: TVService
def build_container() -> AppContainer:
    station_repo = StationRepository()
    session_repo = SessionRepository()
    inventory_repo = InventoryRepository()
    finance_repo = FinanceRepository()
    return AppContainer(stations=StationService(station_repo), sessions=SessionService(session_repo, station_repo), inventory=InventoryService(inventory_repo), finance=FinanceService(finance_repo), auth=AuthService(), license=LicenseService(), tv=TVService())