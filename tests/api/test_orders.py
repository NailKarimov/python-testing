"""Ordering: totals against an independent oracle, coupons, shipping threshold, stock, validation."""

import pytest

from tests.support import Api, Shop, expected_total


@pytest.mark.parametrize(
    ("lines", "coupon", "rate"),
    [
        ([(1, 1)], None, "0"),  # 32.90 + shipping 4.99
        ([(5, 2)], None, "0"),  # 49.90: one cent below free shipping
        ([(5, 2), (12, 1)], None, "0"),  # 69.89: free shipping
        ([(11, 3)], None, "0"),  # 33.33 × 3 = 99.99
        ([(9, 1)], "SAVE10", "0.10"),  # 59.90 − 5.99 = 53.91: still free shipping
        ([(6, 2)], "SAVE10", "0.10"),  # 54.00 − 5.40 = 48.60: the discount pushes it below 50
        ([(11, 1)], "save25", "0.25"),  # coupons are case-insensitive; 8.3325 → 8.33 half up
    ],
    ids=[
        "one-book",
        "49.90-pays-shipping",
        "free-shipping",
        "repeating-decimals",
        "coupon-keeps-free",
        "coupon-loses-free",
        "rounding-half-up",
    ],
)
def test_totals_match_the_oracle(
    customer: Api, guest: Api, lines: list[tuple[int, int]], coupon: str | None, rate: str
) -> None:
    prices = {book_id: guest.book(book_id).json()["price"] for book_id, _ in lines}
    r = customer.order(lines, coupon)
    assert r.status_code == 201, r.text
    order = r.json()
    want = expected_total([(prices[b], q) for b, q in lines], rate)
    assert {k: order[k] for k in want} == want


def test_order_is_readable_by_its_owner(customer: Api) -> None:
    created = customer.order([(2, 1)]).json()
    read = customer.get_order(created["id"])
    assert read.status_code == 200
    assert read.json() == created


def test_the_same_book_twice_becomes_one_line(customer: Api) -> None:
    order = customer.order([(10, 1), (10, 2)]).json()
    assert order["lines"] == [{"book_id": 10, "quantity": 3}]


def test_stock_goes_down_by_the_quantity_ordered(fresh_shop: Shop) -> None:
    api = Api(fresh_shop.url, Api(fresh_shop.url).register("stock@example.test").json()["token"])
    before = api.book(7).json()["stock"]
    assert api.order([(7, 2)]).status_code == 201
    assert api.book(7).json()["stock"] == before - 2


def test_not_enough_stock_reserves_nothing(fresh_shop: Shop) -> None:
    """Book 12 has 1 copy. An order for book 1 plus two copies of book 12 must fail as a whole: book 1 untouched."""
    api = Api(fresh_shop.url, Api(fresh_shop.url).register("atomic@example.test").json()["token"])
    stock_1 = api.book(1).json()["stock"]
    r = api.order([(1, 1), (12, 2)])
    assert r.status_code == 409
    assert r.json() == {"detail": "Not enough stock for book 12"}
    assert api.book(1).json()["stock"] == stock_1
    assert api.book(12).json()["stock"] == 1


def test_last_copy_can_be_bought_once(fresh_shop: Shop) -> None:
    api = Api(fresh_shop.url, Api(fresh_shop.url).register("last@example.test").json()["token"])
    assert api.order([(12, 1)]).status_code == 201
    assert api.book(12).json()["stock"] == 0
    assert api.order([(12, 1)]).status_code == 409


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"lines": []}, 422),
        ({"lines": [{"book_id": 1, "quantity": 0}]}, 422),
        ({"lines": [{"book_id": 1, "quantity": 21}]}, 422),
        ({"lines": [{"book_id": 1, "quantity": 20}]}, 409),  # valid request, only 10 in stock
        ({"lines": [{"book_id": 0, "quantity": 1}]}, 422),
        ({"lines": [{"book_id": 999, "quantity": 1}]}, 404),
        ({"lines": [{"book_id": 1, "quantity": 1}], "coupon": "FREEBOOKS"}, 422),
        ({"lines": [{"book_id": 1, "quantity": "two"}]}, 422),
    ],
    ids=[
        "no-lines",
        "zero-qty",
        "qty-over-20",
        "qty-20-no-stock",
        "book-0",
        "unknown-book",
        "unknown-coupon",
        "qty-not-a-number",
    ],
)
def test_invalid_orders(customer: Api, body: dict[str, object], status: int) -> None:
    r = customer.http.post("/orders", json=body)
    assert r.status_code == status, r.text


def test_email_can_register_only_once_case_insensitive(guest: Api) -> None:
    assert guest.register("Twice@Example.test").status_code == 201
    again = guest.register("twice@example.TEST")
    assert again.status_code == 409
    assert again.json() == {"detail": "Email already registered"}


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "two@@example.test", "x" * 120 + "@example.test"])
def test_invalid_emails_are_rejected(guest: Api, email: str) -> None:
    assert guest.register(email).status_code == 422
