from __future__ import annotations
from typing import Any, List, Optional
from app.db.repositories.inventory import InventoryRepository
class InventoryService:
    def __init__(self, repo: InventoryRepository) -> None:
        self._repo = repo
    @property
    def walkin_station_id(self) -> str:
        return InventoryRepository.WALKIN_STATION_ID
    def drinks(self) -> List[dict[str, Any]]:
        return self._repo.list_drinks()
    def market_products(self) -> List[dict[str, Any]]:
        return self._repo.list_market_products()
    def all_products_for_display(self) -> List[dict[str, Any]]:
        rows = []
        for d in self._repo.list_drinks():
            rows.append({'kind': 'drink', 'drink_name': str(d.get('drink_name') or ''), 'volume': float(d.get('volume') or 0), 'name': f"{d.get('drink_name', '')} {float(d.get('volume') or 0):g} L", 'category': 'Suwlar', 'quantity': int(d.get('quantity') or 0), 'purchase': float(d.get('cost_price') or 0), 'price': float(d.get('price') or 0), 'image': d.get('image')})
        for m in self._repo.list_market_products():
            name = str(m.get('name') or '').strip()
            grams = m.get('grams')
            try:
                g = float(grams or 0)
            except (TypeError, ValueError):
                g = 0.0
            if g > 0 and f'{g:g}' not in name:
                    name = f'{name} {g:g} gr'.strip()
            rows.append({'kind': 'market', 'id': int(m.get('id') or 0), 'name': name, 'category': str(m.get('category') or 'Suzarik'), 'quantity': int(m.get('quantity') or 0), 'purchase': float(m.get('cost_price') or 0), 'price': float(m.get('price') or 0), 'image': m.get('image')})
        from app.db import legacy
        return legacy.module().sort_products_by_bar_order(rows)
    def swap_bar_products(self, product_a: dict[str, Any], product_b: dict[str, Any]) -> None:
        from app.db import legacy
        db = legacy.module()
        products = self.all_products_for_display()
        keys = [db.bar_product_key(p) for p in products]
        db.swap_bar_product_order(db.bar_product_key(product_a), db.bar_product_key(product_b), keys)
    def set_product_image(self, product: dict[str, Any], image: Optional[bytes]) -> None:
        """BAR/katalogdan mahsulot rasmini yangilash."""
        kind = str(product.get('kind') or '')
        if kind == 'drink':
            self._repo.set_drink_image(str(product.get('drink_name') or ''), float(product.get('volume') or 0), image)
        else:
            if kind == 'market':
                self._repo.set_market_image(int(product.get('id') or 0), image)
            else:
                raise ValueError('Noma\'lum mahsulot turi')
    def add_drink_order(self, station_id: str, drink_name: str, volume: float, price: float, session_id: Optional[int]=None) -> None:
        self._repo.add_drink_order(station_id, drink_name, volume, price, session_id)
    def add_market_order(self, station_id: str, product_id: int, session_id: Optional[int]=None, count: int=1) -> None:
        self._repo.add_market_order(station_id, product_id, session_id, count)
    def returnable_orders(self, session_id: Optional[int], station_id: str):
        return self._repo.returnable_orders(session_id, station_id)
    def cancel_order(self, order_id: int) -> bool:
        return self._repo.cancel_order(order_id)