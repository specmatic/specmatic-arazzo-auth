from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import requests

from common.config import settings
from common.vault.client import read_kv2

GRANT_ISSUER = "https://inventory-grant-issuer.example.test"
GRANT_SUBJECT = "inventory-demo-subject"
GRANT_KID = "inventory-grant-key"
CLIENT_AUTH_KID = "inventory-client-auth-key"


class KeycloakAdmin:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()

    def wait_and_login(self) -> None:
        token_url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        for attempt in range(120):
            try:
                response = self.session.post(
                    token_url,
                    data={
                        "grant_type": "password",
                        "client_id": "admin-cli",
                        "username": self.username,
                        "password": self.password,
                    },
                    timeout=3,
                )
                if response.ok:
                    self.session.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
                    self.session.headers["Content-Type"] = "application/json"
                    return
            except requests.RequestException:
                pass
            if attempt == 119:
                raise RuntimeError(f"Keycloak did not become available: {self.base_url}")
            time.sleep(2)

    def request(self, method: str, path: str, body: Any = None, *, tolerate=(200, 201, 204, 409)) -> requests.Response:
        response = self.session.request(
            method,
            f"{self.base_url}/admin/realms{path}",
            json=body,
            timeout=20,
        )
        if response.status_code not in tolerate:
            raise RuntimeError(f"Keycloak admin {method} {path} failed ({response.status_code}): {response.text}")
        return response

    def ensure_realm(self, name: str) -> None:
        self.request(
            "POST",
            "",
            {"realm": name, "enabled": True, "sslRequired": "none", "accessTokenLifespan": 300},
        )

    def ensure_scope(
        self,
        realm: str,
        name: str,
        audience: str | None,
        *,
        include_in_token_scope: bool = True,
    ) -> str:
        scopes = self.request("GET", f"/{realm}/client-scopes", tolerate=(200,)).json()
        found = next((scope for scope in scopes if scope["name"] == name), None)
        if found:
            self.request(
                "PUT",
                f"/{realm}/client-scopes/{found['id']}",
                {
                    **found,
                    "attributes": {
                        **found.get("attributes", {}),
                        "include.in.token.scope": str(include_in_token_scope).lower(),
                        "display.on.consent.screen": "false",
                    },
                    "protocolMappers": self._scope_mappers(name, audience),
                },
                tolerate=(204,),
            )
            return found["id"]
        response = self.request(
            "POST",
            f"/{realm}/client-scopes",
            {
                "name": name,
                "protocol": "openid-connect",
                "attributes": {
                    "include.in.token.scope": str(include_in_token_scope).lower(),
                    "display.on.consent.screen": "false",
                },
                "protocolMappers": self._scope_mappers(name, audience),
            },
            tolerate=(201, 409),
        )
        if response.status_code == 201:
            return response.headers["Location"].rstrip("/").split("/")[-1]
        return self.ensure_scope(realm, name, audience, include_in_token_scope=include_in_token_scope)

    @staticmethod
    def _scope_mappers(name: str, audience: str | None) -> list[dict]:
        if audience is None:
            return []
        return [
            {
                "name": f"{audience}-audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.custom.audience": audience,
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                },
            }
        ]

    def ensure_client(self, realm: str, client: dict) -> str:
        clients = self.request("GET", f"/{realm}/clients", tolerate=(200,)).json()
        found = next((item for item in clients if item["clientId"] == client["clientId"]), None)
        if found:
            client_id = found["id"]
            self.request("PUT", f"/{realm}/clients/{client_id}", {**found, **client}, tolerate=(204,))
            return client_id
        response = self.request("POST", f"/{realm}/clients", client, tolerate=(201, 409))
        if response.status_code == 201:
            return response.headers["Location"].rstrip("/").split("/")[-1]
        return self.ensure_client(realm, client)

    def attach_optional_scope(self, realm: str, client_internal_id: str, scope_id: str) -> None:
        self.request(
            "PUT",
            f"/{realm}/clients/{client_internal_id}/optional-client-scopes/{scope_id}",
            tolerate=(204, 409),
        )

    def attach_default_scope(self, realm: str, client_internal_id: str, scope_id: str) -> None:
        self.request(
            "PUT",
            f"/{realm}/clients/{client_internal_id}/default-client-scopes/{scope_id}",
            tolerate=(204, 409),
        )

    def ensure_user(self, realm: str, username: str, password: str) -> str:
        users = self.request("GET", f"/{realm}/users?username={username}&exact=true", tolerate=(200,)).json()
        if users:
            user_id = users[0]["id"]
        else:
            response = self.request(
                "POST",
                f"/{realm}/users",
                {"username": username, "enabled": True, "emailVerified": True},
                tolerate=(201, 409),
            )
            if response.status_code == 201:
                user_id = response.headers["Location"].rstrip("/").split("/")[-1]
            else:
                return self.ensure_user(realm, username, password)
        self.request(
            "PUT",
            f"/{realm}/users/{user_id}",
            {
                "username": username,
                "email": f"{username}@example.test",
                "firstName": "Demo",
                "lastName": username.removesuffix("-demo-user").title(),
                "enabled": True,
                "emailVerified": True,
                "requiredActions": [],
            },
            tolerate=(204,),
        )
        self.request(
            "PUT",
            f"/{realm}/users/{user_id}/reset-password",
            {"type": "password", "value": password, "temporary": False},
            tolerate=(204,),
        )
        return user_id

    def ensure_federated_identity(self, realm: str, user_id: str, alias: str) -> None:
        self.request(
            "POST",
            f"/{realm}/users/{user_id}/federated-identity/{alias}",
            {"userId": GRANT_SUBJECT, "userName": "inventory-demo-user"},
            tolerate=(204, 409),
        )


def setup_commerce(admin: KeycloakAdmin) -> None:
    realm = "commerce"
    admin.ensure_realm(realm)
    products_scope = admin.ensure_scope(realm, "products:read", None)
    products_audience = admin.ensure_scope(
        realm,
        "products-api-audience",
        "products-api",
        include_in_token_scope=False,
    )
    create_scope = admin.ensure_scope(realm, "orders:create", "orders-api")
    read_scope = admin.ensure_scope(realm, "orders:read", "orders-api")
    products_client = admin.ensure_client(
        realm,
        {
            "clientId": "products-client",
            "enabled": True,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": False,
            "serviceAccountsEnabled": False,
            "fullScopeAllowed": False,
        },
    )
    orders_client = admin.ensure_client(
        realm,
        {
            "clientId": "orders-client",
            "enabled": True,
            "publicClient": False,
            "secret": "demo-orders-client-secret",
            "clientAuthenticatorType": "client-secret",
            "serviceAccountsEnabled": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "fullScopeAllowed": False,
        },
    )
    admin.attach_optional_scope(realm, products_client, products_scope)
    admin.attach_default_scope(realm, products_client, products_audience)
    admin.attach_optional_scope(realm, orders_client, create_scope)
    admin.attach_optional_scope(realm, orders_client, read_scope)
    admin.ensure_user(realm, "products-demo-user", "demo-products-password")


def setup_inventory(admin: KeycloakAdmin, identity_secrets: Mapping[str, str]) -> None:
    realm = "inventory"
    admin.ensure_realm(realm)
    reserve_scope = admin.ensure_scope(realm, "inventory:reserve", None)
    inventory_audience = admin.ensure_scope(
        realm,
        "inventory-api-audience",
        "inventory-api",
        include_in_token_scope=False,
    )

    grant_public_key = identity_secrets["grant_public_key"]
    client_auth_public_key = identity_secrets["client_public_key"]
    idps = admin.request("GET", f"/{realm}/identity-provider/instances", tolerate=(200,)).json()
    idp_config = {
        "issuer": GRANT_ISSUER,
        "useJwksUrl": "false",
        "publicKeySignatureVerifier": grant_public_key,
        "publicKeySignatureVerifierKeyId": GRANT_KID,
        "jwtAuthorizationGrantEnabled": "true",
        "jwtAuthorizationGrantAssertionReuseAllowed": "false",
        "jwtAuthorizationGrantMaxAllowedAssertionExpiration": "300",
        "jwtAuthorizationGrantAssertionSignatureAlg": "RS256",
    }
    idp = next((item for item in idps if item["alias"] == "sample-grant-issuer"), None)
    idp_payload = {
        "alias": "sample-grant-issuer",
        "providerId": "jwt-authorization-grant",
        "enabled": True,
        "trustEmail": True,
        "storeToken": False,
        "config": idp_config,
    }
    if idp:
        admin.request(
            "PUT", f"/{realm}/identity-provider/instances/{idp['alias']}", {**idp, **idp_payload}, tolerate=(204,)
        )
    else:
        admin.request("POST", f"/{realm}/identity-provider/instances", idp_payload, tolerate=(201, 409))

    inventory_client = admin.ensure_client(
        realm,
        {
            "clientId": "inventory-client",
            "enabled": True,
            "publicClient": False,
            "clientAuthenticatorType": "client-jwt",
            "serviceAccountsEnabled": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "fullScopeAllowed": False,
            "attributes": {
                "token.endpoint.auth.method": "private_key_jwt",
                "use.jwks.url": "false",
                "jwt.credential.public.key": client_auth_public_key,
                "jwt.credential.kid": CLIENT_AUTH_KID,
                "oauth2.jwt.authorization.grant.enabled": "true",
                "oauth2.jwt.authorization.grant.idp": "sample-grant-issuer",
            },
        },
    )
    admin.attach_optional_scope(realm, inventory_client, reserve_scope)
    admin.attach_default_scope(realm, inventory_client, inventory_audience)
    user_id = admin.ensure_user(realm, "inventory-demo-user", "demo-inventory-password")
    admin.ensure_federated_identity(realm, user_id, "sample-grant-issuer")
    configure_downscope_policy(admin, realm)


def configure_downscope_policy(admin: KeycloakAdmin, realm: str) -> None:
    profile = {
        "name": "jwt-grant-downscope",
        "description": "Restricts requested scopes to the scope set in the signed grant assertion.",
        "executors": [{"executor": "downscope-assertion-grant-enforcer", "configuration": {}}],
    }
    profiles_url = f"/{realm}/client-policies/profiles"
    existing_profiles = admin.request("GET", profiles_url, tolerate=(200,)).json().get("profiles", [])
    obsolete_profile_names = {"exact-jwt-grant-scope", "jwt-grant-scope-equality"}
    profiles = [
        item for item in existing_profiles if item.get("name") not in obsolete_profile_names | {profile["name"]}
    ]
    profiles.append(profile)
    admin.request("PUT", profiles_url, {"profiles": profiles}, tolerate=(204,))

    policy = {
        "name": "inventory-grant-downscope",
        "description": "Applies Keycloak downscoping to JWT Authorization Grant requests.",
        "enabled": True,
        "conditions": [{"condition": "any-client", "configuration": {}}],
        "profiles": [profile["name"]],
    }
    policies_url = f"/{realm}/client-policies/policies"
    existing_policies = admin.request("GET", policies_url, tolerate=(200,)).json().get("policies", [])
    obsolete_policy_names = {"jwt-grant-scope-equality", "inventory-grant-scope-equality"}
    policies = [item for item in existing_policies if item.get("name") not in obsolete_policy_names | {policy["name"]}]
    policies.append(policy)
    admin.request("PUT", policies_url, {"policies": policies}, tolerate=(204,))


def main() -> None:
    commerce = KeycloakAdmin(settings.commerce_kc_internal, settings.keycloak_admin, settings.keycloak_admin_password)
    inventory = KeycloakAdmin(
        settings.inventory_kc_internal,
        settings.keycloak_admin,
        settings.keycloak_admin_password,
    )
    commerce.wait_and_login()
    setup_commerce(commerce)
    inventory.wait_and_login()
    identity_vault_addr = settings.identity_vault_addr
    identity_vault_token = settings.identity_vault_token
    if identity_vault_addr is None or identity_vault_token is None:
        raise RuntimeError("Identity Vault address and token must be configured for Keycloak bootstrap")

    identity_secrets = read_kv2(identity_vault_addr, identity_vault_token, "inventory")
    setup_inventory(inventory, identity_secrets)
    print(
        "Bootstrapped both realms, static JWT signing keys, federated subject, clients, scopes, and downscope policy."
    )


if __name__ == "__main__":
    main()
