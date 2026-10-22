"""Schemathesis generates requests from the service's own OpenAPI document and checks every response:
no server errors, the status code is documented, the body matches its schema."""

import schemathesis
from hypothesis import settings

from services.bookshop.app import create_app

schema = schemathesis.openapi.from_asgi("/openapi.json", create_app())


@schema.parametrize()
@settings(max_examples=40, deadline=None)
def test_api_conforms_to_its_own_openapi(case: schemathesis.Case) -> None:  # type: ignore[type-arg]
    case.call_and_validate()
