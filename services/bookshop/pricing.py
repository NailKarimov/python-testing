"""Money rules of the bookshop. Kept apart from the web layer so they can be tested on their own (Hypothesis)."""

from decimal import Decimal

CENT = Decimal("0.01")
FREE_SHIPPING_FROM = Decimal("50.00")
SHIPPING = Decimal("4.99")
COUPONS = {"SAVE10": Decimal("0.10"), "SAVE25": Decimal("0.25")}


def money(value: Decimal) -> Decimal:
    """Rounds to cents."""
    return round(value, 2)


def quote(lines: list[tuple[Decimal, int]], coupon: str | None = None) -> dict[str, Decimal]:
    """Prices an order.

    lines: (unit price, quantity). The coupon discount applies to the items, shipping is decided on the
    discounted subtotal: free from 50.00, otherwise 4.99.
    """
    items = money(sum((price * qty for price, qty in lines), Decimal("0")))
    rate = COUPONS.get(coupon.upper(), Decimal("0")) if coupon else Decimal("0")
    discount = money(items * rate)
    subtotal = items - discount
    shipping = Decimal("0.00") if subtotal >= FREE_SHIPPING_FROM or subtotal == 0 else SHIPPING
    return {"items": items, "discount": discount, "shipping": shipping, "total": subtotal + shipping}
