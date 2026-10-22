"""What the API says against what is stored: a second connection reads the SQLite file directly."""

import threading

from tests.support import Api, Shop


def _customer(shop: Shop, email: str) -> Api:
    return Api(shop.url, Api(shop.url).register(email).json()["token"])


def test_an_order_is_stored_with_its_lines_and_the_price_at_the_time(fresh_shop: Shop) -> None:
    api = _customer(fresh_shop, "db@example.test")
    order = api.order([(3, 2), (5, 1)], "SAVE10").json()
    with fresh_shop.db() as db:
        row = db.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
        lines = db.execute(
            "SELECT book_id, quantity, price FROM order_lines WHERE order_id = ? ORDER BY book_id", (order["id"],)
        ).fetchall()
    assert (row["items"], row["discount"], row["shipping"], row["total"], row["coupon"]) == (
        order["items"],
        order["discount"],
        order["shipping"],
        order["total"],
        "SAVE10",
    )
    assert [tuple(r) for r in lines] == [(3, 2, "38.00"), (5, 1, "24.95")]


def test_a_failed_order_leaves_no_trace(fresh_shop: Shop) -> None:
    api = _customer(fresh_shop, "rollback@example.test")
    with fresh_shop.db() as db:
        before = (
            db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            db.execute("SELECT SUM(stock) FROM books").fetchone()[0],
        )
    assert api.order([(1, 1), (9, 3)]).status_code == 409  # book 9 has 2 copies
    with fresh_shop.db() as db:
        after = (
            db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            db.execute("SELECT SUM(stock) FROM books").fetchone()[0],
        )
    assert after == before


def test_concurrent_orders_for_the_last_copies_never_oversell(fresh_shop: Shop) -> None:
    """Book 4 has 3 copies. Ten customers try to buy one each at the same moment: exactly 3 succeed."""
    customers = [_customer(fresh_shop, f"race{i}@example.test") for i in range(10)]
    results: list[int] = []
    start = threading.Barrier(len(customers))

    def buy(api: Api) -> None:
        start.wait()
        results.append(api.order([(4, 1)]).status_code)

    threads = [threading.Thread(target=buy, args=(c,)) for c in customers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [201] * 3 + [409] * 7
    with fresh_shop.db() as db:
        assert db.execute("SELECT stock FROM books WHERE id = 4").fetchone()[0] == 0
        assert db.execute("SELECT SUM(quantity) FROM order_lines WHERE book_id = 4").fetchone()[0] == 3


def test_emails_are_stored_lower_case(fresh_shop: Shop) -> None:
    Api(fresh_shop.url).register("Mixed.Case@Example.TEST")
    with fresh_shop.db() as db:
        assert db.execute("SELECT email FROM customers").fetchone()[0] == "mixed.case@example.test"


def test_reads_and_writes_at_the_same_time_never_fail(fresh_shop: Shop) -> None:
    """Regression for a bug the Locust run found (docs/python.md): one SQLite connection was shared by FastAPI's
    worker threads, and a read running next to a write now and then got an empty row: a 500 in ~0.3 % of
    requests. Functional tests, even the concurrent one above, never saw it. 16 threads mix reads and writes."""
    errors: list[str] = []
    start = threading.Barrier(16)

    def hammer(i: int) -> None:
        api = Api(fresh_shop.url)
        start.wait()
        for n in range(40):
            r = api.books() if n % 3 else api.register(f"t{i}-{n}@example.test")
            if r.status_code >= 500:
                errors.append(f"{r.request.method} {r.request.url.path}: {r.status_code}")

    threads = [threading.Thread(target=hammer, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
