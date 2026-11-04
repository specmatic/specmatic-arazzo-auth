from __future__ import annotations

import time

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from common.config import settings

DEMO_SECRETS = {
    "location_bearer_token": "sample-location-bearer-token",
    "products_client_id": "products-client",
    "products_username": "products-demo-user",
    "products_password": "demo-products-password",
    "orders_client_id": "orders-client",
    "orders_client_secret": "demo-orders-client-secret",
}


def generate_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    return private_pem, public_pem


def write_secret(addr: str, token: str, path: str, data: dict) -> None:
    url = f"{addr.rstrip('/')}/v1/secret/data/{path}"
    for attempt in range(60):
        try:
            response = requests.post(url, headers={"X-Vault-Token": token}, json={"data": data}, timeout=3)
            response.raise_for_status()
            return
        except requests.RequestException:
            if attempt == 59:
                raise
            time.sleep(1)


def main() -> None:
    grant_private_key, grant_public_key = generate_key_pair()
    client_private_key, client_public_key = generate_key_pair()

    write_secret(
        settings.commerce_vault_addr or "http://vault-commerce:8200",
        settings.commerce_vault_token or "commerce-root-token",
        "commerce",
        DEMO_SECRETS,
    )
    write_secret(
        settings.identity_vault_addr or "http://vault-identity:8200",
        settings.identity_vault_token or "identity-root-token",
        "inventory",
        {
            "grant_private_key": grant_private_key,
            "grant_public_key": grant_public_key,
            "grant_kid": "inventory-grant-key",
            "client_private_key": client_private_key,
            "client_public_key": client_public_key,
            "client_kid": "inventory-client-auth-key",
        },
    )
    print("Seeded the Commerce and Identity Vaults with local demo values.")


if __name__ == "__main__":
    main()
