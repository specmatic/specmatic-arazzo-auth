from __future__ import annotations

import pytest
import requests

from tests.contract.config import test_config


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-access-token"], ids=["missing", "invalid"])
def test_location_rejects_missing_or_invalid_bearer(authorization: str | None) -> None:
    headers = {"Authorization": authorization} if authorization else None
    response = requests.get(
        f"{test_config.location_api_url}/location",
        params={"userEmail": "blr@specmatic.io"},
        headers=headers,
        timeout=10,
    )

    assert response.status_code == 401, response.text
    assert set(response.json()) == {"message"}
