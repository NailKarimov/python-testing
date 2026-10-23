# Test plan: Bookshop API (python-testing)

The structure follows ISO/IEC/IEEE 29119-3 (test plan), shortened for one project.

## 1. Context

- **System under test:** the Bookshop API in `services/bookshop`, written with FastAPI and SQLite. It is built for
  this portfolio, so its rules are known and bugs can be planted on purpose.
- **Goal:** show that the money rules, the stock and access control hold for any input and under load. Prove that
  the tests catch real bugs.
- **References:** the service's own OpenAPI document (`/openapi.json`), ISO/IEC 25010, OWASP API Security
  Top 10 (2023).

## 2. Scope

| In scope | Out of scope |
| --- | --- |
| catalogue: list, filters, paging, one book | a UI (the service has none) |
| customers: registration, signed bearer tokens | password storage (there are no passwords) |
| orders: totals, coupons, shipping, stock, reading one's own orders | payments, delivery |
| the published OpenAPI contract | other clients' contracts |
| behaviour under concurrent use and load | long soak tests |

## 3. Quality characteristics (ISO/IEC 25010)

| Characteristic | Covered by |
| --- | --- |
| Functional correctness | API tests, Hypothesis properties against an independent oracle |
| Compatibility (interface) | Schemathesis against the published OpenAPI |
| Security (confidentiality, authenticity) | token, BOLA and header tests |
| Reliability (fault tolerance) | atomic orders, races for the last copies |
| Performance efficiency | Locust with p95 and error-rate budgets |

## 4. Approach

- **Levels:** API and integration with a real server on a free port per pytest-xdist worker. No mocks of the
  service itself.
- **Techniques:**
  - boundary values: page size, prices, the 50.00 shipping threshold;
  - equivalence classes: coupons, tokens;
  - property-based testing with Hypothesis;
  - an independent oracle for totals;
  - generated contract tests with Schemathesis.
- **Test data:** every test creates its own customer. A test that changes stock gets a fresh server
  (`fresh_shop`).
- **Test quality:** `scripts/mutants.py` plants each bug and runs the whole suite. Every bug must fail it.

## 5. Risks

| Risk | Mitigation |
| --- | --- |
| Generated tests are slow or nondeterministic | fixed Hypothesis settings; Schemathesis limited to 40 examples per operation |
| A threading bug only shows under load | the Locust job, plus a 16-thread regression test |
| Floating-point money | `Decimal` everywhere, rounding checked by the oracle |

## 6. Entry and exit criteria

- **Entry:** ruff, ruff format and mypy (strict) pass; the service starts.
- **Exit:** all tests pass; the load budgets hold (p95 300 ms, 500 ms for orders; failures ≤ 1 %); every planted
  bug is caught.

## 7. Deliverables

The test suite, the Allure report on GitHub Pages, [`test-report.md`](test-report.md),
[`python.md`](python.md) and its visual guide.
