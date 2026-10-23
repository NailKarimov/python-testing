# Test summary report: Bookshop API (python-testing)

The structure follows ISO/IEC/IEEE 29119-3 (test completion report), shortened.

- **Period:** 22.10.2026 – 23.10.2026
- **Build:** `main`, latest nightly run in GitHub Actions
- **Allure report:** https://nailkarimov.github.io/python-testing/

## 1. Summary

All 77 tests pass, and the load budgets hold. The tests found five defects in the service. Four of them were
contract gaps and one was a thread-safety bug under load. All five are fixed and covered by regression tests.

## 2. Results

| Metric | Value |
| --- | --- |
| Tests run | 77: 47 API, 6 contract, 7 property, 5 integration, 12 security |
| Passed / failed / skipped | 77 / 0 / 0 |
| Duration | ~16 s on 4 workers |
| Load (Locust, 30 users, 45 s) | 0 failures; p95 within the budgets |
| Mutation check | 11 of 11 planted bugs caught |

## 3. Defects

| ID | Found by | Severity | Summary | Status |
| --- | --- | --- | --- | --- |
| PY-1 | Schemathesis | major | `GET /books/{id}` with id 2^63 answers 500 | fixed: the id range is checked in the path |
| PY-2 | Schemathesis | minor | `max_price` published as "number or string"; `""` and `1e999` valid by the schema | fixed: a string with a strict pattern |
| PY-3 | Schemathesis | minor | the e-mail pattern means different things in Python and JSON Schema | fixed: an ASCII pattern |
| PY-4 | Schemathesis | minor | two shapes of a 422 body | fixed |
| PY-5 | Locust | major | ~0.3 % of requests answer 500 under load: one SQLite connection shared by threads | fixed: a connection per thread, `BEGIN IMMEDIATE`, regression test |

## 4. Deviations from the plan

- Locust runs for 45 s with 30 users. Soak and stress profiles are out of scope here, and microservices-testing
  covers them with k6.

## 5. Recommendations

1. Keep the Hypothesis oracle. It is the only test that catches a wrong rounding mode.
2. Run the load job before any change to the database layer. The thread-safety bug was invisible to functional
   tests.
