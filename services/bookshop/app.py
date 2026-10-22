"""Bookshop API on FastAPI and SQLite.

Customers register and get a bearer token, browse books, place orders (stock is reserved atomically) and read
their own orders. Money travels as strings with two decimals ("12.50"), never as floats.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .pricing import COUPONS, money, quote

SEED = [
    ("Clean Code", "Robert C. Martin", "32.90", 10),
    ("The Pragmatic Programmer", "Andrew Hunt", "41.50", 7),
    ("Lessons Learned in Software Testing", "Cem Kaner", "38.00", 5),
    ("Agile Testing", "Lisa Crispin", "44.99", 3),
    ("Explore It!", "Elisabeth Hendrickson", "24.95", 12),
    ("Accelerate", "Nicole Forsgren", "27.00", 8),
    ("Refactoring", "Martin Fowler", "47.20", 6),
    ("Working Effectively with Legacy Code", "Michael Feathers", "45.00", 4),
    ("Domain-Driven Design", "Eric Evans", "59.90", 2),
    ("Release It!", "Michael Nygard", "36.40", 9),
    ("Test-Driven Development", "Kent Beck", "33.33", 11),
    ("Perfect Software", "Gerald Weinberg", "19.99", 1),
]


class Book(BaseModel):
    id: int
    title: str
    author: str
    price: str = Field(pattern=r"^\d+\.\d{2}$")
    stock: int = Field(ge=0)


class BookPage(BaseModel):
    items: list[Book]
    total: int
    page: int
    size: int


class Registration(BaseModel):
    # ASCII on purpose: "\s" in Python and in the JSON Schema (ECMA) dialect disagree on characters like U+0085,
    # so a published pattern with "\s" accepted e-mails the service rejected (found by Schemathesis).
    email: str = Field(
        min_length=3, max_length=120, pattern=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$"
    )


class Token(BaseModel):
    customer_id: int
    token: str


class OrderLine(BaseModel):
    book_id: int = Field(gt=0, le=2**63 - 1)
    quantity: int = Field(gt=0, le=20)


class OrderRequest(BaseModel):
    lines: list[OrderLine] = Field(min_length=1, max_length=20)
    coupon: str | None = Field(default=None, max_length=20)

    @field_validator("coupon")
    @classmethod
    def known_coupon(cls, v: str | None) -> str | None:
        # A validation error like any other field, so every 422 of this endpoint has the same documented shape.
        if v is not None and v.upper() not in COUPONS:
            raise ValueError("Unknown coupon")
        return v


class Order(BaseModel):
    id: int
    customer_id: int
    lines: list[OrderLine]
    items: str
    discount: str
    shipping: str
    total: str


class Problem(BaseModel):
    detail: str


def create_app(db_path: str = ":memory:", secret: bytes | None = None) -> FastAPI:
    """One app, one database. Tests start a fresh app per test session (or per test that needs isolation)."""
    secret = secret or secrets.token_bytes(32)
    # One SQLite connection per worker thread. FastAPI runs these handlers in a thread pool, and a single shared
    # connection let a read run next to a write and now and then return an empty row: a 500 that the Locust run
    # found and tests/integration/test_database.py now reproduces. ":memory:" becomes a named shared-cache
    # database so every thread sees the same data.
    uri = (
        f"file:bookshop-{secrets.token_hex(4)}?mode=memory&cache=shared" if db_path == ":memory:" else f"file:{db_path}"
    )
    local = threading.local()

    def connect() -> sqlite3.Connection:
        c = sqlite3.connect(uri, uri=True, check_same_thread=False, isolation_level=None, timeout=10)
        c.row_factory = sqlite3.Row
        if db_path != ":memory:":
            c.execute("PRAGMA journal_mode=WAL")
        return c

    keeper = connect()  # keeps a shared in-memory database alive for the app's lifetime

    class _PerThread:
        def __getattr__(self, name: str) -> object:
            if not hasattr(local, "conn"):
                local.conn = connect()
            return getattr(local.conn, name)

    conn: sqlite3.Connection = _PerThread()  # type: ignore[assignment]
    keeper.executescript(
        """
        CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY, title TEXT, author TEXT, price TEXT, stock INTEGER
            CHECK (stock >= 0));
        CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, email TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer_id INTEGER, items TEXT, discount TEXT,
            shipping TEXT, total TEXT, coupon TEXT);
        CREATE TABLE IF NOT EXISTS order_lines (order_id INTEGER, book_id INTEGER, quantity INTEGER, price TEXT);
        """
    )
    if keeper.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
        keeper.executemany("INSERT INTO books (title, author, price, stock) VALUES (?, ?, ?, ?)", SEED)

    # 400: a body that is not JSON at all (FastAPI answers it before validation); documented so clients expect it.
    app = FastAPI(title="Bookshop API", version="1.0.0", responses={400: {"model": Problem}, 401: {"model": Problem}})
    app.state.db = keeper

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(Exception)
    async def no_stack_traces(request: Request, exc: Exception) -> JSONResponse:
        # Never show internals to the client; the detail stays in the server log.
        return JSONResponse(status_code=500, content={"detail": "Internal error"})

    def sign(customer_id: int) -> str:
        mac = hmac.new(secret, str(customer_id).encode(), hashlib.sha256).hexdigest()
        return f"{customer_id}.{mac}"

    def customer(authorization: Annotated[str | None, Header()] = None) -> int:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
        token = authorization.removeprefix("Bearer ")
        cid, _, _ = token.partition(".")
        if not cid.isdigit() or not hmac.compare_digest(sign(int(cid)), token):
            raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"})
        return int(cid)

    def row_to_book(r: sqlite3.Row) -> Book:
        return Book(id=r["id"], title=r["title"], author=r["author"], price=r["price"], stock=r["stock"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/books", response_model=BookPage)
    def list_books(
        author: str | None = Query(default=None, max_length=80),
        # A string with a strict pattern, not Decimal: Schemathesis showed that Decimal's published schema
        # ("number or string") promised more than the service accepts ("" and "1e999" were "valid").
        max_price: str | None = Query(default=None, pattern=r"^\d{1,6}(\.\d{1,2})?$"),
        page: int = Query(default=1, ge=1),
        size: int = Query(default=10, ge=1, le=50),
    ) -> BookPage:
        rows = [row_to_book(r) for r in conn.execute("SELECT * FROM books ORDER BY id")]
        if author:
            rows = [b for b in rows if author.lower() in b.author.lower()]
        if max_price is not None:
            rows = [b for b in rows if Decimal(b.price) <= Decimal(max_price)]
        start = (page - 1) * size
        return BookPage(items=rows[start : start + size], total=len(rows), page=page, size=size)

    @app.get("/books/{book_id}", response_model=Book, responses={404: {"model": Problem}})
    # Ids fit SQLite's 64-bit integer; a larger one used to crash the lookup with a 500 (found by Schemathesis).
    def get_book(book_id: int = Path(ge=1, le=2**63 - 1)) -> Book:
        r = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if not r:
            raise HTTPException(404, "No such book")
        return row_to_book(r)

    @app.post("/customers", response_model=Token, status_code=201, responses={409: {"model": Problem}})
    def register(body: Registration) -> Token:
        try:
            cur = conn.execute("INSERT INTO customers (email) VALUES (?)", (body.email.lower(),))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Email already registered") from None
        cid = int(cur.lastrowid or 0)
        return Token(customer_id=cid, token=sign(cid))

    def load_order(order_id: int) -> Order | None:
        o = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not o:
            return None
        lines = [
            OrderLine(book_id=r["book_id"], quantity=r["quantity"])
            for r in conn.execute("SELECT * FROM order_lines WHERE order_id = ?", (order_id,))
        ]
        return Order(
            id=o["id"],
            customer_id=o["customer_id"],
            lines=lines,
            items=o["items"],
            discount=o["discount"],
            shipping=o["shipping"],
            total=o["total"],
        )

    @app.post(
        "/orders",
        response_model=Order,
        status_code=201,
        responses={404: {"model": Problem}, 409: {"model": Problem}},
    )
    def place_order(body: OrderRequest, cid: Annotated[int, Depends(customer)]) -> Order:
        wanted: dict[int, int] = {}
        for line in body.lines:  # the same book twice is one line with the sum
            wanted[line.book_id] = wanted.get(line.book_id, 0) + line.quantity
        # All-or-nothing: BEGIN IMMEDIATE takes SQLite's write lock before reading stock, so two orders for the last
        # copy cannot both see it in stock (tests/integration: ten customers, three copies).
        conn.execute("BEGIN IMMEDIATE")
        try:
            priced: list[tuple[Decimal, int]] = []
            for book_id, qty in wanted.items():
                r = conn.execute("SELECT price, stock FROM books WHERE id = ?", (book_id,)).fetchone()
                if not r:
                    raise HTTPException(404, f"No such book: {book_id}")
                if r["stock"] < qty:
                    raise HTTPException(409, f"Not enough stock for book {book_id}")
                conn.execute("UPDATE books SET stock = stock - ? WHERE id = ?", (qty, book_id))
                priced.append((Decimal(r["price"]), qty))
            q = quote(priced, body.coupon)
            cur = conn.execute(
                "INSERT INTO orders (customer_id, items, discount, shipping, total, coupon) VALUES (?,?,?,?,?,?)",
                (cid, *(str(money(q[k])) for k in ("items", "discount", "shipping", "total")), body.coupon),
            )
            order_id = int(cur.lastrowid or 0)
            for book_id, qty in wanted.items():
                price = conn.execute("SELECT price FROM books WHERE id = ?", (book_id,)).fetchone()["price"]
                conn.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)", (order_id, book_id, qty, price))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        order = load_order(order_id)
        assert order
        return order

    @app.get("/orders/{order_id}", response_model=Order, responses={404: {"model": Problem}})
    def get_order(cid: Annotated[int, Depends(customer)], order_id: int = Path(ge=1, le=2**63 - 1)) -> Order:
        order = load_order(order_id)
        # Someone else's order is "not found", not "forbidden": the id space is not confirmed to a stranger.
        if not order or order.customer_id != cid:
            raise HTTPException(404, "No such order")
        return order

    return app


app = create_app(os.environ.get("BOOKSHOP_DB", ":memory:"))
