"""Reads Locust's CSV statistics and checks them against the budgets (SLOs). Exit code 1 if any is broken.

python scripts/load_check.py load-results/run_stats.csv >> "$GITHUB_STEP_SUMMARY"
"""

import csv
import sys

BUDGET_P95_MS = {"default": 300, "POST /orders": 500}
MAX_FAILURE_RATIO = 0.01


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    broken = []
    print("## Locust: Bookshop load test\n")
    print("| Endpoint | Requests | Failures | p50, ms | p95, ms | p99, ms | Budget p95 | |")
    print("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        name = r["Name"]
        if name == "Aggregated":
            continue
        reqs, fails = int(r["Request Count"]), int(r["Failure Count"])
        p95 = float(r["95%"]) if r["95%"] not in ("", "N/A") else 0.0
        budget = BUDGET_P95_MS.get(name, BUDGET_P95_MS["default"])
        ok = p95 <= budget
        if not ok:
            broken.append(f"{name}: p95 {p95:.0f} ms > {budget} ms")
        print(f"| {name} | {reqs} | {fails} | {r['50%']} | {p95:.0f} | {r['99%']} | {budget} | {'✓' if ok else '✗'} |")
    total = next(r for r in rows if r["Name"] == "Aggregated")
    ratio = int(total["Failure Count"]) / max(1, int(total["Request Count"]))
    print(
        f"\nTotal: {total['Request Count']} requests, {float(total['Requests/s']):.1f} req/s, "
        f"failures {ratio:.2%} (budget {MAX_FAILURE_RATIO:.0%})."
    )
    if ratio > MAX_FAILURE_RATIO:
        broken.append(f"failure ratio {ratio:.2%} > {MAX_FAILURE_RATIO:.0%}")
    for b in broken:
        print(f"\n**Budget broken:** {b}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "load-results/run_stats.csv"))
