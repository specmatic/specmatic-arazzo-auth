from __future__ import annotations

import uuid

import pytest

from tests.contract.config import test_config

ORDER_BODY = {"userId": 1, "productId": 1, "inventory": 1}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        pytest.param("POST", "/orders", ORDER_BODY, id="create-order"),
        pytest.param("GET", "/orders/9001", None, id="get-order-detail"),
    ],
)
@pytest.mark.parametrize("authorization", [None, "Bearer invalid-access-token"], ids=["missing", "invalid"])
def test_orders_reject_missing_or_invalid_bearer(
    method: str,
    path: str,
    body: dict | None,
    authorization: str | None,
) -> None:
    headers = {"requestId": str(uuid.uuid4())}
    if authorization:
        headers["Authorization"] = authorization

    response = test_config.request(
        method,
        f"{test_config.orders_api_url}{path}",
        json=body,
        headers=headers,
    )

    assert response.status_code == 401, response.text
    assert set(response.json()) == {"message"}
