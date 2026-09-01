from __future__ import annotations
from typing import Any, List, Optional
from app.db import legacy
class InventoryRepository:
    """Ichimliklar, market va buyurtmalar."""
    WALKIN_STATION_ID = 'DOKON'
    def list_drinks(self) -> List[dict[str, Any]]:
        return legacy.module().get_drink_prices()
    def list_market_products(self) -> List[dict[str, Any]]:
        return legacy.module().get_market_products()
    def add_drink_order(self, station_id: str, drink_name: str, volume: float, price: float, session_id: Optional[int]=None) -> None:
        legacy.module().add_drink_order(station_id, drink_name, volume, price, session_id)
    def add_market_order(self, station_id: str, product_id: int, session_id: Optional[int]=None, count: int=1) -> None:
        legacy.module().add_market_order(station_id, product_id, session_id, count)
    def returnable_orders(self, session_id: Optional[int], station_id: str):
        return legacy.module().get_returnable_orders_grouped(session_id, station_id)
    def cancel_order(self, order_id: int) -> bool:
        return bool(legacy.module().cancel_order_and_return_stock(order_id))
    def set_drink_image(self, drink_name: str, volume: float, image: Optional[bytes]) -> None:
        legacy.module().set_drink_image(drink_name, volume, image)
    def set_market_image(self, product_id: int, image: Optional[bytes]) -> None:
        legacy.module().update_market_product(product_id, image=image, update_image=True)