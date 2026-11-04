from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    commerce_issuer: str = "http://localhost:9002/realms/commerce"
    inventory_issuer: str = "http://localhost:9001/realms/inventory"
    database_url: str = "postgresql://sample:sample@localhost:5432/sample_db"
    commerce_jwks_url: str = "http://localhost:9002/realms/commerce/protocol/openid-connect/certs"
    inventory_jwks_url: str = "http://localhost:9001/realms/inventory/protocol/openid-connect/certs"
    location_bearer_token: str = "local-location-bearer-token"
    commerce_vault_addr: str | None = None
    commerce_vault_token: str | None = None
    identity_vault_addr: str | None = None
    identity_vault_token: str | None = None
    keycloak_admin: str = "admin"
    keycloak_admin_password: str = "admin"
    commerce_kc_internal: str = "http://keycloak-commerce:8080"
    inventory_kc_internal: str = "http://keycloak-inventory:8080"


settings = Settings()

COMMERCE_ISSUER = settings.commerce_issuer
INVENTORY_ISSUER = settings.inventory_issuer
DATABASE_URL = settings.database_url
COMMERCE_JWKS_URL = settings.commerce_jwks_url
INVENTORY_JWKS_URL = settings.inventory_jwks_url
