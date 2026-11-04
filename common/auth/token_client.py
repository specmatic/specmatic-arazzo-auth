from __future__ import annotations

import base64
import time
import uuid

import jwt
import requests

from common.vault.client import read_kv2

GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
GRANT_ISSUER = "https://inventory-grant-issuer.example.test"
GRANT_SUBJECT = "inventory-demo-subject"
INVENTORY_CLIENT_ID = "inventory-client"


def commerce_token(
    token_url: str,
    *,
    grant_type: str,
    scope: str | None,
    client_id: str,
    client_secret: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> str:
    data = {"grant_type": grant_type, "client_id": client_id}
    if scope is not None:
        data["scope"] = scope
    auth = None
    if username is not None and password is not None:
        data.update({"username": username, "password": password})
    elif client_secret is not None:
        auth = (client_id, client_secret)
    response = requests.post(token_url, data=data, auth=auth, timeout=10)
    response.raise_for_status()
    return response.json()["access_token"]


def _tamper_signature(token: str) -> str:
    header, payload, signature = token.split(".")
    raw = bytearray(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
    raw[0] ^= 0x01
    changed = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()
    return f"{header}.{payload}.{changed}"


def inventory_assertions(
    token_url: str,
    secrets: dict,
    *,
    client_id: str = INVENTORY_CLIENT_ID,
    grant_scope: str | None,
    invalid_grant_signature: bool = False,
    invalid_client_signature: bool = False,
    grant_jti: str | None = None,
) -> dict[str, str]:
    now = int(time.time())
    issuer = token_url.rsplit("/protocol/openid-connect/token", 1)[0]
    grant_claims = {
        "iss": GRANT_ISSUER,
        "sub": GRANT_SUBJECT,
        "aud": issuer,
        "iat": now,
        "exp": now + 240,
        "jti": grant_jti or str(uuid.uuid4()),
    }
    if grant_scope is not None:
        grant_claims["scope"] = grant_scope
    grant_assertion = jwt.encode(
        grant_claims,
        secrets["grant_private_key"],
        algorithm="RS256",
        headers={"kid": secrets["grant_kid"], "typ": "JWT"},
    )

    client_claims = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_url,
        "iat": now,
        "exp": now + 120,
        "jti": str(uuid.uuid4()),
    }
    client_assertion = jwt.encode(
        client_claims,
        secrets["client_private_key"],
        algorithm="RS256",
        headers={"kid": secrets["client_kid"], "typ": "JWT"},
    )
    if invalid_grant_signature:
        grant_assertion = _tamper_signature(grant_assertion)
    if invalid_client_signature:
        client_assertion = _tamper_signature(client_assertion)
    return {"grant_assertion": grant_assertion, "client_assertion": client_assertion}


def post_inventory_token(
    token_url: str,
    secrets: dict,
    *,
    client_id: str = INVENTORY_CLIENT_ID,
    requested_scope: str | None,
    grant_scope: str | None,
    invalid_grant_signature: bool = False,
    invalid_client_signature: bool = False,
    include_grant_assertion: bool = True,
    include_client_assertion: bool = True,
    grant_jti: str | None = None,
    grant_assertion: str | None = None,
) -> requests.Response:
    assertions = inventory_assertions(
        token_url,
        secrets,
        client_id=client_id,
        grant_scope=grant_scope,
        invalid_grant_signature=invalid_grant_signature,
        invalid_client_signature=invalid_client_signature,
        grant_jti=grant_jti,
    )
    if grant_assertion is not None:
        assertions["grant_assertion"] = grant_assertion
    form = {
        "client_id": client_id,
        "grant_type": GRANT_TYPE,
        "client_assertion_type": CLIENT_ASSERTION_TYPE,
    }
    if requested_scope is not None:
        form["scope"] = requested_scope
    if include_grant_assertion:
        form["assertion"] = assertions["grant_assertion"]
    if include_client_assertion:
        form["client_assertion"] = assertions["client_assertion"]
    return requests.post(token_url, data=form, timeout=10)


def read_secret(addr: str, token: str, path: str) -> dict:
    return read_kv2(addr, token, path)
