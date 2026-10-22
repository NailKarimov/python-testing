"""Test helpers: a real HTTP server in a thread, an API client, and an independent price oracle."""

import socket
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
import uvicorn

from services.bookshop.app import create_app


@dataclass
class Shop:
    url: str
    db_path: Path

    def db(self) -> sqlite3.Connection:
        """A second connection straight to the database: the tests check what was really stored."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def running_shop(db_path: Path) -> Iterator[Shop]:
    """Starts the Bookshop on a free port with its own SQLite file, the way it runs for real (over HTTP)."""
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(str(db_path)), host="127.0.0.1", port=port, log_level="warning", server_header=False)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("Bookshop did not start")
        time.sleep(0.02)
    try:
        yield Shop(url=f"http://127.0.0.1:{port}", db_path=db_path)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


class Api:
    """Thin client: one method per endpoint, raw httpx responses so tests see status codes and headers."""

    def __init__(self, base_url: str, token: str | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(base_url=base_url, headers=headers, timeout=10)

    def books(self, **params: str | int | None) -> httpx.Response:
        return self.http.get("/books", params={k: v for k, v in params.items() if v is not None})

    def book(self, book_id: int) -> httpx.Response:
        return self.http.get(f"/books/{book_id}")

    def register(self, email: str) -> httpx.Response:
        return self.http.post("/customers", json={"email": email})

    def order(self, lines: list[tuple[int, int]], coupon: str | None = None) -> httpx.Response:
        body: dict[str, object] = {"lines": [{"book_id": b, "quantity": q} for b, q in lines]}
        if coupon is not None:
            body["coupon"] = coupon
        return self.http.post("/orders", json=body)

    def get_order(self, order_id: int) -> httpx.Response:
        return self.http.get(f"/orders/{order_id}")


def expected_total(lines: list[tuple[str, int]], coupon_rate: str = "0") -> dict[str, str]:
    """Oracle, written separately from the service: what a person with a calculator gets.

    Items = Σ price × qty; discount = items × rate, rounded half up to cents; shipping 4.99 below 50.00 after
    the discount, free from 50.00; total = items − discount + shipping.
    """
    cent = Decimal("0.01")
    items = sum((Decimal(p) * q for p, q in lines), Decimal(0)).quantize(cent, ROUND_HALF_UP)
    discount = (items * Decimal(coupon_rate)).quantize(cent, ROUND_HALF_UP)
    after = items - discount
    shipping = Decimal("0.00") if after >= Decimal("50") else Decimal("4.99")
    return {"items": str(items), "discount": str(discount), "shipping": str(shipping), "total": str(after + shipping)}
