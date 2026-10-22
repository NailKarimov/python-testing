"""Mutation check: plants one bug at a time in the Bookshop and runs the tests; every bug must make them fail.

python scripts/mutants.py            # all mutants
python scripts/mutants.py M3 M5      # some
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUTANTS = [
    (
        "M1",
        "services/bookshop/pricing.py",
        "rounding=ROUND_HALF_UP",
        'rounding="ROUND_HALF_EVEN"',
        "banker's rounding instead of half up",
    ),
    (
        "M2",
        "services/bookshop/pricing.py",
        "subtotal >= FREE_SHIPPING_FROM",
        "subtotal > FREE_SHIPPING_FROM",
        "free shipping from 50.01 instead of 50.00",
    ),
    (
        "M3",
        "services/bookshop/pricing.py",
        "if subtotal >= FREE_SHIPPING_FROM",
        "if items >= FREE_SHIPPING_FROM",
        "shipping decided before the discount",
    ),
    (
        "M4",
        "services/bookshop/pricing.py",
        "COUPONS.get(coupon.upper()",
        "COUPONS.get(coupon",
        "coupons become case-sensitive",
    ),
    ("M5", "services/bookshop/app.py", 'if r["stock"] < qty:', "if False:", "no stock check"),
    (
        "M6",
        "services/bookshop/app.py",
        "if not order or order.customer_id != cid:",
        "if not order:",
        "any customer can read any order (BOLA)",
    ),
    (
        "M7",
        "services/bookshop/app.py",
        "not hmac.compare_digest(sign(int(cid)), token)",
        "False",
        "the token signature is not checked",
    ),
    (
        "M8",
        "services/bookshop/app.py",
        'response.headers["X-Content-Type-Options"] = "nosniff"',
        "pass",
        "nosniff header dropped",
    ),
    (
        "M9",
        "services/bookshop/app.py",
        "size: int = Query(default=10, ge=1, le=50)",
        "size: int = Query(default=10, ge=1, le=500)",
        "page size not capped at 50",
    ),
    ("M10", "services/bookshop/app.py", "(body.email.lower(),)", "(body.email,)", "e-mails stored as typed"),
    (
        "M11",
        "services/bookshop/app.py",
        'conn.execute("BEGIN IMMEDIATE")',
        'conn.execute("BEGIN")',
        "a deferred transaction: stock is read before the write lock is taken",
    ),
]


def run(selected: set[str]) -> int:
    survived = []
    for mid, file, old, new, what in MUTANTS:
        if selected and mid not in selected:
            continue
        path = ROOT / file
        original = path.read_text()
        if original.count(old) != 1:
            raise SystemExit(f"{mid}: '{old}' must occur exactly once in {file}")
        path.write_text(original.replace(old, new))
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "4"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            path.write_text(original)
        caught = result.returncode != 0
        failed = [ln.split(" ")[1] for ln in result.stdout.splitlines() if ln.startswith("FAILED")][:2]
        print(f"{mid:4} {'caught  ' if caught else 'SURVIVED'} {what}  {', '.join(failed)}")
        if not caught:
            survived.append(mid)
    print(f"\n{len(survived)} survived" if survived else "\nAll mutants caught.")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(run(set(sys.argv[1:])))
