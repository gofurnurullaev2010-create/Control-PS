from __future__ import annotations
from typing import Any, List, Optional
from app.db import legacy
class FinanceRepository:
    """Qarzdorlar, bronlar, xarajatlar, operator hisobotlari."""
    def list_debtors(self, search: str='', day: Optional[str]=None, include_paid: bool=False) -> List[dict[str, Any]]:
        return legacy.module().list_debtors(search, day, include_paid)
    def debtor_day_summary(self, include_paid: bool=False):
        return legacy.module().debtor_day_summary(include_paid)
    def add_debtor(self, client_name: str, phone: str, amount: float, note: str='') -> int:
        return int(legacy.module().add_debtor(client_name, phone, amount, note))
    def adjust_debtor(self, debtor_id: int, delta: float) -> float:
        return float(legacy.module().adjust_debtor_amount(debtor_id, delta))
    def mark_debtor_paid(self, debtor_id: int, paid: bool=True) -> None:
        legacy.module().mark_debtor_paid(debtor_id, paid)
    def list_bookings(self, search: str='', include_closed: bool=False):
        return legacy.module().list_bookings(search, include_closed)
    def add_booking(self, client_name: str, phone: str, station_id: str, booking_time: str, note: str='') -> int:
        return int(legacy.module().add_booking(client_name, phone, station_id, booking_time, note))
    def list_expenses(self, search: str='', day: Optional[str]=None):
        return legacy.module().list_expenses(search, day)
    def expense_day_summary(self, keep_days: int=30):
        return legacy.module().expense_day_summary(keep_days)
    def list_current_period_expenses(self, search: str=''):
        return legacy.module().list_current_period_expenses(search)
    def add_expense(self, expense_type: str, amount: float, wallet: str='cash', note: str='') -> int:
        return int(legacy.module().add_expense(expense_type, amount, wallet, note))
    def update_expense(self, expense_id: int, expense_type: str, amount: float) -> dict[str, Any]:
        return legacy.module().update_expense(expense_id, expense_type, amount)
    def expense_total_for_day(self, day: Optional[str]=None) -> float:
        return float(legacy.module().expense_total_for_day(day))
    def operator_report_for_day(self, day: Optional[str]=None) -> dict[str, Any]:
        return legacy.module().operator_report_for_day(day)
    def save_operator_report(self, operator_index: int, report: dict[str, Any]) -> int:
        return int(legacy.module().save_operator_report(operator_index, report))
    def revenue_split_for_day(self, day: str) -> dict[str, float]:
        return legacy.module().revenue_split_for_day(day)
    def revenue_total_all_time(self) -> float:
        return float(legacy.module().revenue_total_all_time())
    def current_business_date(self):
        return legacy.module().current_business_date()