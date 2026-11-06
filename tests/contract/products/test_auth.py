from __future__ import annotations

import pytest

from tests.contract.config import test_config


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-access-token"], ids=["missing", "invalid"])
def test_products_rejects_missing_or_invalid_bearer(authorization: str | None) -> None:
    headers = {"Authorization": authorization} if authorization else None
    response = test_config.request(
        "GET",
        f"{test_config.products_api_url}/products",
        params={"locationCode": "IND-BLR"},
        headers=headers,
    )

    assert response.status_code == 401, response.text
    assert set(response.json()) == {"message"}
