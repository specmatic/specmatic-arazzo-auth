from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from common.config import COMMERCE_ISSUER, COMMERCE_JWKS_URL, INVENTORY_ISSUER, INVENTORY_JWKS_URL

bearer = HTTPBearer(auto_error=False)


def _http_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"message": message})


def verify_access_token(
    credentials: HTTPAuthorizationCredentials | None,
    *,
    issuer: str,
    jwks_url: str,
    audience: str,
    required_scope: str | None = None,
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _http_error(status.HTTP_401_UNAUTHORIZED, "A bearer access token is required")
    try:
        key = PyJWKClient(jwks_url, cache_keys=True).get_signing_key_from_jwt(credentials.credentials).key
        claims = jwt.decode(
            credentials.credentials,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except Exception as error:
        raise _http_error(status.HTTP_401_UNAUTHORIZED, "The bearer access token is invalid") from error

    scopes = set(str(claims.get("scope", "")).split())
    if required_scope and required_scope not in scopes:
        raise _http_error(status.HTTP_403_FORBIDDEN, f"Access token does not include {required_scope}")
    return claims


def commerce_auth(audience: str, scope: str) -> Callable:
    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
        return verify_access_token(
            credentials,
            issuer=COMMERCE_ISSUER,
            jwks_url=COMMERCE_JWKS_URL,
            audience=audience,
            required_scope=scope,
        )

    return dependency


def inventory_auth(scope: str) -> Callable:
    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
        return verify_access_token(
            credentials,
            issuer=INVENTORY_ISSUER,
            jwks_url=INVENTORY_JWKS_URL,
            audience="inventory-api",
            required_scope=scope,
        )

    return dependency
