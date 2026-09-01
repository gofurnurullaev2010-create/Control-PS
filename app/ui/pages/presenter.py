"""Sahifa ma\'lumotlarini service qatlami orqali yig\'ish."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, List, Optional
from app.core.container import AppContainer
def fmt_dt(value: str) -> str:
    if 'T' in value:
        d, t = value.split('T', 1)
        return f'{d} г. {t[:8]}'
    else:
        return value
class PagePresenter:
    def __init__(self, container: AppContainer) -> None:
        self._c = container
    def active_rows(self, cards) -> List[list[object]]:
        rows = []
        for card in cards.values():
            if card._busy or card._tv_viewing:
                rows.append(['-', card.display_name(), 'Ko\'rilmekte' if card._busy else 'TV', card._col_played.text(), card._col_total.text()])
        return rows
    def product_rows(self, warehouse: bool=False) -> List[list[object]]:
        rows = []
        for item in self._c.inventory.all_products_for_display():
            if warehouse:
                rows.append(['', item['name'], item['quantity'], item['purchase'], item['price']])
            else:
                rows.append([item['name'], item['category'], item['quantity'], item['purchase'], item['price']])
        return rows
    def income_rows(self) -> List[list[object]]:
        rows = []
        for r in self._c.sessions.daily_report():
            s_time = str(r.get('start_time') or '').split('T')[(-1)][:5]
            e_time = str(r.get('end_time') or '').split('T')[(-1)][:5]
            rows.append([r.get('station_id', ''), f'{s_time} - {e_time}', f"{r.get('duration_minutes', 0)} min", r.get('drinks') or '-', float(r.get('revenue') or 0)])
        return rows
    def debtor_rows(self, search: str) -> List[list[object]]:
        rows = []
        for r in self._c.finance.debtors(search):
            name = str(r.get('client_name', ''))
            phone = str(r.get('phone') or '')
            if phone:
                name = f'{name} - {phone}'
            rows.append([name, float(r.get('amount') or 0), fmt_dt(str(r.get('debt_time') or '')), r.get('note') or ''])
        return rows
    def booking_rows(self, search: str) -> List[list[object]]:
        rows = []
        for r in self._c.finance.bookings(search):
            rows.append([str(r.get('client_name') or ''), str(r.get('station_id') or ''), fmt_dt(str(r.get('booking_time') or '')), str(r.get('phone') or ''), str(r.get('note') or '')])
        return rows
    def expense_rows(self, search: str) -> List[list[object]]:
        rows = []
        for r in self._c.finance.expenses(search):
            rows.append([str(r.get('expense_type') or ''), float(r.get('amount') or 0), 'Ceyf puli' if str(r.get('wallet') or '') == 'safe' else 'Kassa puli', str(r.get('note') or ''), fmt_dt(str(r.get('created_time') or ''))])
        return rows
    def client_rows(self) -> List[list[object]]:
        rows = []
        for i, c in enumerate(self._c.finance.clients_from_debtors()):
            rows.append([i + 1, c['name'], c['phone'], float(c['debt'] or 0), fmt_dt(str(c['time'] or ''))])
        return rows
    def balance(self) -> dict[str, float]:
        return self._c.finance.balance_summary()
    def today_revenue(self) -> float:
        return self._c.sessions.today_revenue()