from __future__ import annotations

import base64
import json

import pytest
import requests

from common.auth.token_client import inventory_assertions, post_inventory_token
from tests.contract.config import test_config


def decode_payload(token: str) -> dict[str, object]:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def update_inventory(access_token: str, order_id: int = 9001) -> requests.Response:
    return requests.put(
        f"{test_config.inventory_api_url}/inventory",
        params={"orderId": order_id},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )


@pytest.fixture(scope="module")
def inventory_secrets() -> dict[str, str]:
    return test_config.identity_secrets()


@pytest.fixture(scope="module", autouse=True)
def reset_sample_data() -> None:
    test_config.reset_sample_data()


class TestJwtGrantScopeDownscoping:
    @pytest.mark.parametrize(
        ("requested_scope", "grant_scope", "order_id"),
        [
            pytest.param("inventory:reserve", "inventory:reserve", 9001, id="equal-scopes"),
            pytest.param("inventory:reserve", "inventory:reserve profile", 9003, id="proper-subset"),
        ],
    )
    def test_both_jwts_issue_token_and_token_authorizes_inventory(
        self,
        inventory_secrets: dict,
        requested_scope: str,
        grant_scope: str,
        order_id: int,
    ) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope=requested_scope,
            grant_scope=grant_scope,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["token_type"].lower() == "bearer"
        assert isinstance(body["access_token"], str) and body["access_token"]
        claims = decode_payload(body["access_token"])
        assert claims["iss"] == test_config.inventory_issuer
        audience = claims["aud"]
        assert "inventory-api" in ({audience} if isinstance(audience, str) else set(audience))
        assert "inventory:reserve" in set(claims["scope"].split())

        inventory_response = update_inventory(body["access_token"], order_id)
        assert inventory_response.status_code == 200, inventory_response.text
        assert inventory_response.content == b""

    def test_requested_scope_not_present_in_grant_is_rejected(self, inventory_secrets: dict) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="inventory:reserve profile",
            grant_scope="inventory:reserve",
        )
        assert response.status_code == 400, response.text
        assert response.json().get("error") == "invalid_scope"

    def test_omitted_scope_cannot_authorize_inventory_even_with_default_scopes(self, inventory_secrets: dict) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope=None,
            grant_scope="inventory:reserve",
        )
        if response.status_code == 200:
            claims = decode_payload(response.json()["access_token"])
            assert "inventory:reserve" not in set(claims.get("scope", "").split())
            audience = claims.get("aud", [])
            audience_set = {audience} if isinstance(audience, str) else set(audience)
            assert "inventory-api" in audience_set
            api_response = update_inventory(response.json()["access_token"])
            assert api_response.status_code == 403, api_response.text
        else:
            assert response.status_code == 400, response.text
            assert response.json().get("error") in {"invalid_scope", "invalid_request"}

    def test_valid_token_without_inventory_scope_is_denied_by_inventory_api(self, inventory_secrets: dict) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="profile",
            grant_scope="profile",
        )
        assert response.status_code == 200, response.text
        claims = decode_payload(response.json()["access_token"])
        assert "inventory:reserve" not in set(claims.get("scope", "").split())
        assert update_inventory(response.json()["access_token"]).status_code == 403


class TestJwtAssertionValidation:
    def test_invalid_grant_assertion_with_valid_client_assertion_is_rejected(self, inventory_secrets: dict) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="inventory:reserve",
            grant_scope="inventory:reserve",
            invalid_grant_signature=True,
        )
        assert response.status_code != 200, response.text
        assert response.json().get("error") in {"invalid_grant", "invalid_request"}

    def test_valid_grant_assertion_with_invalid_client_assertion_is_rejected(self, inventory_secrets: dict) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="inventory:reserve",
            grant_scope="inventory:reserve",
            invalid_client_signature=True,
        )
        assert response.status_code != 200, response.text
        assert response.json().get("error") == "invalid_client"

    @pytest.mark.parametrize(
        ("include_grant_assertion", "include_client_assertion", "expected_error"),
        [
            pytest.param(False, True, "invalid_grant", id="missing-grant-assertion"),
            pytest.param(True, False, "invalid_client", id="missing-client-assertion"),
        ],
    )
    def test_each_assertion_is_required(
        self,
        inventory_secrets: dict,
        include_grant_assertion: bool,
        include_client_assertion: bool,
        expected_error: str,
    ) -> None:
        response = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="inventory:reserve",
            grant_scope="inventory:reserve",
            include_grant_assertion=include_grant_assertion,
            include_client_assertion=include_client_assertion,
        )
        assert response.status_code != 200, response.text
        assert response.json().get("error") == expected_error

    def test_grant_assertion_replay_is_rejected_with_fresh_client_assertion(self, inventory_secrets: dict) -> None:
        assertions = inventory_assertions(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            grant_scope="inventory:reserve",
        )
        first = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="inventory:reserve",
            grant_scope="inventory:reserve",
            grant_assertion=assertions["grant_assertion"],
        )
        assert first.status_code == 200, first.text

        replay = post_inventory_token(
            test_config.inventory_token_url,
            inventory_secrets,
            client_id=test_config.inventory_client_id,
            requested_scope="inventory:reserve",
            grant_scope="inventory:reserve",
            grant_assertion=assertions["grant_assertion"],
        )
        assert replay.status_code != 200, replay.text
        assert replay.json().get("error") in {"invalid_grant", "invalid_request"}
