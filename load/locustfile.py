"""Locust load test for the Bookshop: browsing customers and buying customers, in Python.

locust -f load/locustfile.py --headless -u 30 -r 10 -t 45s --host http://127.0.0.1:8000 --csv load-results/run
python scripts/load_check.py load-results/run_stats.csv     # p95 and error-rate budgets (SLOs)
"""

import random
import uuid

from locust import HttpUser, between, task


class Browser(HttpUser):
    """Most visitors only look: the catalogue, a filter, one book."""

    weight = 4
    wait_time = between(0.2, 1.0)

    @task(3)
    def catalogue(self) -> None:
        self.client.get(f"/books?page={random.randint(1, 2)}&size=10", name="GET /books")

    @task(2)
    def filtered(self) -> None:
        author = random.choice(["martin", "michael", "beck", "kaner"])
        self.client.get(f"/books?author={author}", name="GET /books?author")

    @task(2)
    def one_book(self) -> None:
        self.client.get(f"/books/{random.randint(1, 12)}", name="GET /books/{id}")


class Buyer(HttpUser):
    """Some register and buy. Running out of stock (409) is a correct answer, not a failure."""

    weight = 1
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        r = self.client.post(
            "/customers", json={"email": f"load-{uuid.uuid4().hex[:12]}@example.test"}, name="POST /customers"
        )
        self.client.headers["Authorization"] = f"Bearer {r.json()['token']}"

    @task
    def buy(self) -> None:
        body = {"lines": [{"book_id": random.randint(1, 12), "quantity": 1}]}
        with self.client.post("/orders", json=body, name="POST /orders", catch_response=True) as r:
            if r.status_code in (201, 409):
                r.success()
                if r.status_code == 201:
                    self.client.get(f"/orders/{r.json()['id']}", name="GET /orders/{id}")
            else:
                r.failure(f"unexpected {r.status_code}")
