# python-testing

[![Tests](https://github.com/NailKarimov/python-testing/actions/workflows/tests.yml/badge.svg)](https://github.com/NailKarimov/python-testing/actions/workflows/tests.yml)
[![Allure report](https://img.shields.io/badge/report-Allure-orange)](https://nailkarimov.github.io/python-testing/)
[![Release](https://img.shields.io/github/v/release/NailKarimov/python-testing)](https://github.com/NailKarimov/python-testing/releases)

### ▶ Open online

| Page | What it is |
| --- | --- |
| **[Allure test report](https://nailkarimov.github.io/python-testing/)** | latest CI run |
| [Python tests](https://nailkarimov.github.io/python-testing/python.html) | interactive guide |

Click these links: opening an `.html` file in the file list shows its source code, GitHub does not run it.

API, contract, property-based, integration, security and load tests **in Python**. They run against a Bookshop
API of our own, written with FastAPI and SQLite.

| | |
| --- | --- |
| **System under test** | own Bookshop API (`services/bookshop`): catalogue, customers with signed tokens, orders with coupons and stock |
| **Language and tools** | Python 3.13 · pytest + httpx · Hypothesis · Schemathesis · Locust · Allure · ruff · mypy (strict) |
| **Types of testing** | functional API, contract (OpenAPI), property-based, database integration, security, load |
| **Tests** | 77 (pytest, 4 workers, ~16 s) + a Locust load job |
| **Test quality** | 11/11 planted bugs caught (`scripts/mutants.py`) |
| **Reports** | [Allure](https://nailkarimov.github.io/python-testing/) · [visual guide](https://nailkarimov.github.io/python-testing/python.html) |

## What is tested

| Suite | Tool | What it proves |
| --- | --- | --- |
| `tests/api/test_catalogue.py` | pytest + httpx | listing, filters with boundaries, paging covers every book once, page-size limits, responses match the published OpenAPI schema |
| `tests/api/test_orders.py` | pytest + httpx | totals against an independent oracle (shipping threshold, coupons, half-up rounding), stock goes down, an order that cannot be filled reserves nothing, validation, e-mails unique case-insensitively |
| `tests/contract/test_openapi_fuzz.py` | Schemathesis | generated requests for every operation: no 5xx, documented status codes, bodies match the schema |
| `tests/property/test_pricing.py` | Hypothesis | 7 rules that hold for every basket, and agreement with the oracle |
| `tests/integration/test_database.py` | pytest + SQLite | the stored order and lines; a failed order leaves no trace; 10 customers race for 3 copies; reads and writes together never fail |
| `tests/security/test_access.py` | pytest | 401 for missing, malformed and forged tokens; another customer's order is 404 (BOLA); security headers; no internals in errors; quotes in filters are data |
| `load/locustfile.py` | Locust | browsers and buyers; p95 and error-rate budgets checked by `scripts/load_check.py` |

## Findings

These bugs are recorded as closed issues in [Issues](https://github.com/NailKarimov/python-testing/issues?q=is%3Aissue+is%3Aclosed+label%3Abug), each with steps, expected and actual results and the fix.

| Found by | Defect in our own service | Fix |
| --- | --- | --- |
| Schemathesis | `GET /books/2^63` reached SQLite and answered 500 | ids limited to 1 … 2^63 − 1 in the path |
| Schemathesis | `max_price` was published as "number or string", so `""` and `1e999` were valid by the schema | a string with a strict pattern |
| Schemathesis | the e-mail pattern used `\s`, which Python and JSON Schema read differently | an ASCII pattern |
| Schemathesis | two shapes of a 422 body | the coupon is validated like any field |
| **Locust** | ~0.3 % of requests failed with 500 under load: one SQLite connection was shared by worker threads; every functional test passed | a connection per thread, `BEGIN IMMEDIATE`, and a 16-thread regression test |

Banker's rounding (mutant M1) is caught **only** by the Hypothesis oracle: none of the hand-picked baskets has an
exact half cent.

## Running it

Requirements: Python 3.13; Java 17+ only for a local Allure report.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -n 4                                   # everything
pytest tests/property --hypothesis-show-statistics
python scripts/mutants.py                     # mutation check
uvicorn services.bookshop.app:app --port 8000 &
locust -f load/locustfile.py --headless -u 30 -r 10 -t 45s --host http://127.0.0.1:8000 --csv load-results/run
python scripts/load_check.py load-results/run_stats.csv
ruff check . && ruff format --check . && mypy services tests
```

## Project structure

```text
services/bookshop/     the system under test: FastAPI app, pricing rules
tests/support.py       a real uvicorn server per worker, API client, the totals oracle
tests/conftest.py      fixtures: shop, fresh_shop, guest, customer, new_customer
tests/api/             functional API tests
tests/contract/        Schemathesis against the service's own OpenAPI
tests/property/        Hypothesis properties of the money rules
tests/integration/     what is really stored in SQLite, races
tests/security/        tokens, BOLA, headers, error bodies
load/                  Locust scenarios
scripts/               load budgets, mutation check
docs/                  test plan, test report, guides
```

## CI

`.github/workflows/tests.yml` runs on push, pull request, nightly at 03:00 UTC and on demand:
- the `test` job runs ruff, mypy and `pytest -n 4`, then publishes the Allure report with history to GitHub Pages;
- the `load` job runs Locust for 45 s against the running service and writes the p95 and error-rate budgets to
  the job summary.

Releases: committing `.github/releases/<tag>.md` runs the Release workflow, which creates the tag and the GitHub release with that file as its notes.

## Documentation

| Document | What it is |
| --- | --- |
| [`docs/test-plan.md`](docs/test-plan.md) | test plan (ISO/IEC/IEEE 29119-3) |
| [`docs/test-report.md`](docs/test-report.md) | test summary report: latest results, defects, recommendations |
| [`docs/python.md`](docs/python.md) | guide: what Python adds, what the tests found, the mutation table |
| [`docs/python.html`](https://nailkarimov.github.io/python-testing/python.html) | the same guide, interactive: rounding calculator, contract gaps, the threading bug |

## Part of a portfolio

One of 13 test automation projects by [Nail Karimov](https://github.com/NailKarimov):
[all projects](https://github.com/NailKarimov) ·
[testing map](https://nailkarimov.github.io/api-test-automation/testing-map.html) ·
[toolbox](https://nailkarimov.github.io/api-test-automation/toolbox.html).
