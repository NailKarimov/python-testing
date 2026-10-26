"""Property-based tests of the money rules (Hypothesis): instead of a few hand-picked baskets, thousands of
generated ones, each checked against rules that must hold for every basket."""

from decimal import Decimal

from hypothesis import example, given, note
from hypothesis import strategies as st

from services.bookshop.pricing import COUPONS, FREE_SHIPPING_FROM, SHIPPING, quote

prices = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("500.00"), places=2)
lines = st.lists(st.tuples(prices, st.integers(min_value=1, max_value=20)), min_size=1, max_size=10)
coupons = st.sampled_from([None, *COUPONS, *(c.lower() for c in COUPONS)])


@given(lines, coupons)
def test_total_is_items_minus_discount_plus_shipping(basket: list[tuple[Decimal, int]], coupon: str | None) -> None:
    q = quote(basket, coupon)
    assert q["total"] == q["items"] - q["discount"] + q["shipping"]


@given(lines, coupons)
def test_every_amount_is_in_whole_cents_and_never_negative(
    basket: list[tuple[Decimal, int]], coupon: str | None
) -> None:
    for name, value in quote(basket, coupon).items():
        assert value >= 0, name
        assert value == value.quantize(Decimal("0.01")), name


@given(lines, coupons)
@example([(Decimal("49.99"), 1)], None)  # one cent below the threshold
@example([(Decimal("50.00"), 1)], None)  # exactly the threshold
@example([(Decimal("55.56"), 1)], "SAVE10")  # 55.56 − 5.56 = 50.00 after the discount
def test_shipping_is_free_exactly_from_50_after_discount(basket: list[tuple[Decimal, int]], coupon: str | None) -> None:
    q = quote(basket, coupon)
    after = q["items"] - q["discount"]
    assert q["shipping"] == (Decimal("0.00") if after >= FREE_SHIPPING_FROM else SHIPPING)


@given(lines)
def test_a_coupon_never_makes_the_items_dearer_and_the_bigger_coupon_saves_more(
    basket: list[tuple[Decimal, int]],
) -> None:
    none, ten, quarter = (quote(basket, c) for c in (None, "SAVE10", "SAVE25"))
    assert none["discount"] == 0
    assert 0 <= ten["discount"] <= quarter["discount"] <= none["items"]


@given(lines, coupons)
def test_order_of_lines_does_not_change_the_price(basket: list[tuple[Decimal, int]], coupon: str | None) -> None:
    assert quote(basket, coupon) == quote(list(reversed(basket)), coupon)


@given(prices, st.integers(min_value=1, max_value=20), st.integers(min_value=1, max_value=20))
def test_splitting_a_line_in_two_costs_the_same(price: Decimal, a: int, b: int) -> None:
    assert quote([(price, a + b)]) == quote([(price, a), (price, b)])


@given(lines, coupons)
def test_service_pricing_agrees_with_the_independent_oracle(
    basket: list[tuple[Decimal, int]], coupon: str | None
) -> None:
    """The oracle in tests/support.py is written separately; Hypothesis looks for any basket where they differ."""
    from tests.support import expected_total

    rate = {None: "0", "SAVE10": "0.10", "SAVE25": "0.25"}[coupon.upper() if coupon else None]
    want = expected_total([(str(p), q) for p, q in basket], rate)
    got = {k: str(v) for k, v in quote(basket, coupon).items()}
    note(f"basket: {[(str(p), q) for p, q in basket]}, coupon: {coupon}")
    note(f"service: {got}")
    note(f"oracle:  {want}")
    assert got == want
