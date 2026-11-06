from __future__ import annotations

import pytest

from tests.contract.config import test_config


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-access-token"], ids=["missing", "invalid"])
def test_inventory_rejects_missing_or_invalid_bearer(authorization: str | None) -> None:
    headers = {"Authorization": authorization} if authorization else None
    response = test_config.request(
        "PUT",
        f"{test_config.inventory_api_url}/inventory",
        params={"orderId": 9001},
        headers=headers,
    )

    assert response.status_code == 401, response.text
    assert set(response.json()) == {"message"}
