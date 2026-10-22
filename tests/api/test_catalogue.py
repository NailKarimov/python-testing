"""Browsing: list, filters, paging bounds, one book, and responses that match the published OpenAPI schema."""

from decimal import Decimal

import jsonschema
import pytest

from services.bookshop.app import SEED
from tests.support import Api


def test_first_page_lists_books_in_id_order_with_money_as_strings(guest: Api) -> None:
    r = guest.books()
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(SEED)
    assert [b["id"] for b in body["items"]] == list(range(1, 11))
    assert all(isinstance(b["price"], str) and len(b["price"].split(".")[1]) == 2 for b in body["items"])


@pytest.mark.parametrize(
    ("params", "expected_titles"),
    [
        ({"author": "fowler"}, ["Refactoring"]),  # case-insensitive substring
        ({"author": "MICHAEL"}, ["Working Effectively with Legacy Code", "Release It!"]),
        ({"max_price": "24.95"}, ["Explore It!", "Perfect Software"]),  # the boundary itself is included
        ({"max_price": "24.94"}, ["Perfect Software"]),
        ({"author": "nobody"}, []),
    ],
    ids=["author", "author-two-matches", "max-price-boundary", "max-price-just-below", "no-match"],
)
def test_filters(guest: Api, params: dict[str, str], expected_titles: list[str]) -> None:
    body = guest.books(size=50, **params).json()
    assert [b["title"] for b in body["items"]] == expected_titles
    assert body["total"] == len(expected_titles)


def test_paging_covers_every_book_exactly_once(guest: Api) -> None:
    seen = []
    for page in (1, 2, 3):
        seen += [b["id"] for b in guest.books(page=page, size=5).json()["items"]]
    assert seen == list(range(1, len(SEED) + 1))
    assert guest.books(page=4, size=5).json()["items"] == []


@pytest.mark.parametrize(("size", "status"), [(0, 422), (1, 200), (50, 200), (51, 422)])
def test_page_size_boundaries(guest: Api, size: int, status: int) -> None:
    assert guest.books(size=size).status_code == status


@pytest.mark.parametrize("bad", ["-1", "abc", "1e999", "", "12.345"])
def test_invalid_max_price_is_rejected(guest: Api, bad: str) -> None:
    assert guest.books(max_price=bad).status_code == 422


@pytest.mark.parametrize("book_id", ["0", "-1", "9223372036854775808"])
def test_book_ids_outside_the_valid_range_are_rejected_not_crashing(guest: Api, book_id: str) -> None:
    # 2**63 used to reach SQLite and fail with a 500 (found by Schemathesis, see docs/python.md)
    assert guest.http.get(f"/books/{book_id}").status_code == 422


def test_one_book_and_a_missing_one(guest: Api) -> None:
    book = guest.book(3).json()
    assert book["title"] == "Lessons Learned in Software Testing"
    assert Decimal(book["price"]) == Decimal("38.00")
    missing = guest.book(9999)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "No such book"}


def _inline(node: object, schemas: dict[str, object]) -> object:
    """Replaces every {"$ref": "#/components/schemas/X"} with the schema itself, so jsonschema can check it."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            return _inline(schemas[ref.rsplit("/", 1)[1]], schemas)
        return {k: _inline(v, schemas) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline(v, schemas) for v in node]
    return node


def test_responses_match_the_published_openapi_schema(guest: Api) -> None:
    """The service publishes /openapi.json; real responses must match it (the contract other teams code against)."""
    schemas = guest.http.get("/openapi.json").json()["components"]["schemas"]
    jsonschema.validate(guest.books().json(), _inline(schemas["BookPage"], schemas))
    jsonschema.validate(guest.book(1).json(), _inline(schemas["Book"], schemas))
