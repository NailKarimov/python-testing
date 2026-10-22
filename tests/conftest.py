import uuid
from collections.abc import Iterator
from pathlib import Path

import allure
import pytest

from tests.support import Api, Shop, running_shop


@pytest.fixture(scope="session")
def shop(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Shop]:
    """One Bookshop per test session (per xdist worker), on its own SQLite file."""
    with running_shop(tmp_path_factory.mktemp("shop") / "bookshop.db") as s:
        yield s


@pytest.fixture
def fresh_shop(tmp_path: Path) -> Iterator[Shop]:
    """A Bookshop of its own, for tests that change stock and must not see other tests' orders."""
    with running_shop(tmp_path / "bookshop.db") as s:
        yield s


@pytest.fixture
def guest(shop: Shop) -> Iterator[Api]:
    api = Api(shop.url)
    yield api
    api.http.close()


def _customer(url: str) -> Api:
    email = f"qa-{uuid.uuid4().hex[:10]}@example.test"
    token = Api(url).register(email).json()["token"]
    return Api(url, token)


@pytest.fixture
def customer(shop: Shop) -> Api:
    """A newly registered customer with a bearer token."""
    return _customer(shop.url)


@pytest.fixture
def new_customer() -> object:
    """Factory for more customers (two people at once)."""
    return _customer


@pytest.fixture(autouse=True)
def _allure_labels(request: pytest.FixtureRequest) -> None:
    allure.dynamic.label("owner", "Nail Karimov")
    allure.dynamic.parent_suite("Bookshop API")
    allure.dynamic.suite(request.node.module.__name__.split(".")[1])
