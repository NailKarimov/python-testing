# python-testing

[![Tests](https://github.com/NailKarimov/python-testing/actions/workflows/tests.yml/badge.svg)](https://github.com/NailKarimov/python-testing/actions/workflows/tests.yml)
[![Allure report](https://img.shields.io/badge/report-Allure-orange)](https://nailkarimov.github.io/python-testing/)

API, contract, property-based, integration, security and load tests **in Python** on a Bookshop API of our own
(FastAPI + SQLite): pytest, httpx, **Hypothesis**, **Schemathesis**, **Locust**, Allure, ruff and mypy (strict).

| Spec | What it proves |
| --- | --- |
| `api/test_catalogue` | listing, filters with boundaries, paging covers every book once, page-size limits, responses match the published OpenAPI schema |
| `api/test_orders` | totals against an independent oracle (shipping threshold, coupons, half-up rounding), stock goes down, an order that cannot be filled reserves nothing, validation, e-mails unique case-insensitively |
| `contract/test_openapi_fuzz` | Schemathesis: generated requests for every operation, no 5xx, documented status codes, bodies match the schema |
| `property/test_pricing` | Hypothesis: 7 rules that hold for every basket, and agreement with the oracle |
| `integration/test_database` | the stored order and lines, a failed order leaves no trace, 10 customers race for 3 copies, reads and writes together never fail |
| `security/test_access` | 401 for missing, malformed and forged tokens, another customer's order is 404 (BOLA), security headers, no internals in errors, quotes in filters are data |
| `load/locustfile.py` | Locust: browsers and buyers, p95 and error-rate budgets (CI job) |

**What the tests found in our own service:** four contract gaps from Schemathesis (a 500 on a 64-bit id, a
too-generous `Decimal` schema, a regex that means different things in Python and JSON Schema…) and a
thread-safety bug from Locust: one SQLite connection shared by worker threads made 0.3 % of requests fail under
load while every functional test passed. **Mutation check:** 11 planted bugs, all caught; banker's rounding only by
the Hypothesis oracle. Details: [`docs/python.md`](docs/python.md) · visual guide:
[`docs/python.html`](https://nailkarimov.github.io/python-testing/python.html).

## Running it

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
pytest -n 4
python scripts/mutants.py
```

Part of a QA portfolio: [github.com/NailKarimov](https://github.com/NailKarimov).
