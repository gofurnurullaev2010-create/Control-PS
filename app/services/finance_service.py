from __future__ import annotations
from typing import Any, List, Optional
from app.db.repositories.finance import FinanceRepository
class FinanceService:
    def __init__(self, repo: FinanceRepository) -> None:
        self._repo = repo
    def debtors(self, search: str='', day: Optional[str]=None) -> List[dict[str, Any]]:
        return self._repo.list_debtors(search, day)
    def add_debtor(self, client_name: str, phone: str, amount: float, note: str='') -> int:
        return self._repo.add_debtor(client_name, phone, amount, note)
    def adjust_debtor(self, debtor_id: int, delta: float) -> float:
        return self._repo.adjust_debtor(debtor_id, delta)
    def mark_debtor_paid(self, debtor_id: int, paid: bool=True) -> None:
        self._repo.mark_debtor_paid(debtor_id, paid)
    def bookings(self, search: str='') -> List[dict[str, Any]]:
        return self._repo.list_bookings(search)
    def add_booking(self, client_name: str, phone: str, station_id: str, booking_time: str, note: str='') -> int:
        return self._repo.add_booking(client_name, phone, station_id, booking_time, note)
    def expenses(self, search: str='') -> List[dict[str, Any]]:
        return self._repo.list_expenses(search)
    def add_expense(self, expense_type: str, amount: float, wallet: str='cash', note: str='') -> int:
        return self._repo.add_expense(expense_type, amount, wallet, note)
    def balance_summary(self) -> dict[str, float]:
        """Balans: Kassa = jabıw kutilgan summa; Ceyf; Uliwmalıq = ceyf+kassa."""
        try:
            from app.db import legacy
            db = legacy.module()
            report = db.operator_report_for_day()
            cash = float(report.get('expected_amount') or 0)
            safe = float(db.get_safe_balance())
            expenses = float(report.get('expense_total') or 0)
            debt = float(report.get('debt_total') or 0) - float(report.get('debt_paid_total') or 0)
        except Exception:
            day = self._repo.current_business_date().isoformat()
            cash = float(self._repo.revenue_split_for_day(day).get('total') or 0)
            safe = 0.0
            expenses = 0.0
            debt = 0.0
        return {'total': safe + cash, 'safe': safe, 'cash': cash, 'expenses': expenses, 'debt': debt}
    def operator_report(self, day: Optional[str]=None) -> dict[str, Any]:
        return self._repo.operator_report_for_day(day)
    def save_operator_report(self, operator_index: int, report: dict[str, Any]) -> int:
        return self._repo.save_operator_report(operator_index, report)
    def clients_from_debtors(self) -> List[dict[str, Any]]:
        clients = {}
        for r in self._repo.list_debtors('', include_paid=True):
            key = (str(r.get('client_name') or ''), str(r.get('phone') or ''))
            item = clients.setdefault(key, {'name': key[0], 'phone': key[1], 'debt': 0.0, 'time': str(r.get('debt_time') or '')})
            if not r.get('paid'):
                item['debt'] = float(item.get('debt') or 0) + float(r.get('amount') or 0)
        return list(clients.values())