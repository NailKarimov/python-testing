"""Access control and safe responses on our own service: tokens, other customers' data, headers, errors."""

import pytest

from tests.support import Api, Shop


@pytest.mark.parametrize(
    "header",
    [None, "Bearer", "Basic abc", "Bearer 1.deadbeef", "Bearer abc.def", "Bearer 1."],
    ids=["none", "empty-bearer", "basic", "wrong-signature", "non-numeric-id", "no-signature"],
)
def test_orders_need_a_valid_token(shop: Shop, header: str | None) -> None:
    api = Api(shop.url)
    if header is not None:
        api.http.headers["Authorization"] = header
    r = api.order([(1, 1)])
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_a_token_cannot_be_moved_to_another_customer(shop: Shop, customer: Api) -> None:
    """The signature covers the customer id: changing the id in someone's token must not work."""
    token = customer.http.headers["Authorization"].removeprefix("Bearer ")
    cid, sig = token.split(".")
    forged = Api(shop.url, f"{int(cid) + 1}.{sig}")
    assert forged.order([(1, 1)]).status_code == 401


def test_another_customers_order_is_not_found(shop: Shop, new_customer) -> None:  # type: ignore[no-untyped-def]
    """BOLA (OWASP API1): knowing an order id is not enough. 404 rather than 403, so ids are not confirmed."""
    alice, bob = new_customer(shop.url), new_customer(shop.url)
    order_id = alice.order([(2, 1)]).json()["id"]
    r = bob.get_order(order_id)
    assert r.status_code == 404
    assert r.json() == {"detail": "No such order"}
    assert bob.get_order(10_000_000).json() == r.json()  # the same answer as for an id that does not exist


def test_security_headers_on_every_response(guest: Api) -> None:
    for r in (guest.books(), guest.book(9999), guest.http.get("/health")):
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["Cache-Control"] == "no-store"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert "server" not in r.headers  # no product name and version for an attacker to look up


def test_bad_input_does_not_reveal_internals(guest: Api) -> None:
    """Malformed JSON gets a validation error naming the field, not a stack trace or SQL."""
    r = guest.http.post("/customers", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    text = r.text.lower()
    for leak in ("traceback", "sqlite", "/home/"):
        assert leak not in text


@pytest.mark.parametrize("value", ["' OR 1=1 --", "Robert'); DROP TABLE books;--"])
def test_text_filters_are_data_not_sql(guest: Api, value: str) -> None:
    """Filter values are compared as text, so quotes in them change nothing and break nothing."""
    r = guest.books(author=value)
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert guest.books().json()["total"] == 12  # and the catalogue is still all there
