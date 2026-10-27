from types import SimpleNamespace
from app.routers.orders import can_view_orders


def test_can_view_orders_roles():
    for r in ("finance", "manager", "business_head", "ceo", "super_admin"):
        assert can_view_orders(SimpleNamespace(role=r)), r
    for r in ("rep", "inside_sales", "pre_sales"):
        assert not can_view_orders(SimpleNamespace(role=r)), r
