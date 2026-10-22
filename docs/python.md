# Testing in Python: what the stack adds

The same kinds of checks as the TypeScript repositories of this portfolio, written in Python, on a service of our
own: the **Bookshop API** (FastAPI + SQLite, `services/bookshop/`). Customers register and get a signed bearer
token, browse 12 books, order with coupons (10 % / 25 %), pay 4.99 shipping below 50.00; stock is reserved
all-or-nothing.

| Layer | Tool | Where | Tests |
| --- | --- | --- | ---: |
| API | pytest + httpx, a real server on a free port per worker | `tests/api/` | 47 |
| Contract | Schemathesis on the service's own `/openapi.json` | `tests/contract/` | 6 operations × 40 examples |
| Property-based | Hypothesis on the money rules | `tests/property/` | 7 properties |
| Integration | a second SQLite connection reads what was really stored | `tests/integration/` | 5 |
| Security | tokens, BOLA, headers, error bodies, quotes in filters | `tests/security/` | 12 |
| Load | Locust, browsers and buyers, budgets checked by a script | `load/`, `scripts/load_check.py` | CI job |

77 tests in 16 s on 4 workers (pytest-xdist); Allure report on GitHub Pages.

## 1. What Python is good at here

- **Hypothesis**: instead of seven hand-picked baskets, thousands of generated ones, each checked against a rule
  that must always hold (total = items − discount + shipping; amounts in whole cents; free shipping exactly from
  50.00 after the discount; splitting a line costs the same) and against an independent oracle. When a property
  fails, Hypothesis shrinks the basket to the smallest one that still fails.
- **Schemathesis**: written in Python, so it runs inside pytest against the ASGI app directly, with no server.
- **Locust**: load scenarios are plain Python classes (`Browser` with weight 4, `Buyer` with weight 1), so the
  rule "running out of stock (409) is a correct answer, not a failure" is one `if`.
- **pytest fixtures**: `shop` (one server per worker), `fresh_shop` (a server of its own for a test that changes
  stock), `customer`, `new_customer` (a factory for two people at once).

## 2. What the tests found in our own service

| Found by | What | Fix |
| --- | --- | --- |
| Schemathesis | `max_price` was a `Decimal`, published as "number **or string**": `""` and `1e999` were valid by the schema and rejected or mishandled by the service | a string with a strict pattern |
| Schemathesis | `GET /books/9223372036854775808` (2^63) reached SQLite and crashed with a **500** | ids limited to 1 … 2^63 − 1 in the path |
| Schemathesis | the e-mail pattern used `\s`, which Python and the JSON Schema (ECMA) dialect read differently (U+0085): e-mails valid by the published schema were rejected | an ASCII pattern |
| Schemathesis | an unknown coupon answered 422 with `{"detail": "…"}`, other 422s with a list: two shapes for one status | the coupon is validated like any field |
| **Locust** | **~0.3 % of requests failed with 500 under load**: one SQLite connection was shared by FastAPI's worker threads, and a read next to a write sometimes got an empty row. Every functional test passed, including the concurrent oversell test | a connection per thread; `tests/integration` now reproduces the bug (16 threads mixing reads and writes) and failed 3 times out of 3 before the fix |

The last row is the reason load tests belong in a test suite: the bug needed real concurrency and a few
thousand requests to show, and once seen, a 30-line regression test catches it every time.

## 3. Does the suite catch bugs? (mutation check)

`python scripts/mutants.py` plants 11 bugs one at a time and runs the suite: all 11 caught.

| Id | Planted bug | Caught by |
| --- | --- | --- |
| M1 | banker's rounding instead of half up | **only** the Hypothesis property "service agrees with the oracle": none of the hand-picked baskets has an exact half cent |
| M2 | free shipping from 50.01 | Hypothesis, with the explicit example 50.00 |
| M3 | shipping decided before the discount | totals table, "coupon-loses-free" |
| M4 | coupons case-sensitive | totals table, `save25` |
| M5 | no stock check | last copy, invalid orders |
| M6 | any customer reads any order (BOLA) | security |
| M7 | token signature not checked | security, forged tokens |
| M8 | `nosniff` dropped | security headers |
| M9 | page size not capped | boundary 51 → 422 |
| M10 | e-mails stored as typed | duplicate e-mail, the stored row |
| M11 | deferred transaction (stock read before the write lock) | 10 customers race for 3 copies |

Two lessons from building this table. The first M1 replaced the rounding constant with a name that was not
imported, so every order crashed and the mutant was "caught" for the wrong reason; a mutant has to be a working
program with a wrong rule. And after the thread-safety fix an extra `threading.Lock` around orders became
redundant (SQLite's `BEGIN IMMEDIATE` already serialises them): removing it was an equivalent mutant, so the lock
went, and the mutant now weakens the transaction instead.

## 4. Running it

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
pytest -n 4                                  # everything, about 16 s
pytest tests/property --hypothesis-show-statistics
python scripts/mutants.py                    # mutation check, a few minutes
uvicorn services.bookshop.app:app --port 8000 &
locust -f load/locustfile.py --headless -u 30 -r 10 -t 45s --host http://127.0.0.1:8000 --csv load-results/run
python scripts/load_check.py load-results/run_stats.csv
```
