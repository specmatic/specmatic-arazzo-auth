from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, ClassVar

import requests
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from testcontainers.core.container import DockerContainer

from common.auth.token_client import commerce_token, post_inventory_token, read_secret
from scripts.seed_data import seed

ROOT = Path(__file__).resolve().parents[2]
JWT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{20,}\."
    r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
)


class TestConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env.test", ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_root: ClassVar[Path] = ROOT

    database_url: str
    location_api_url: str
    products_api_url: str
    orders_api_url: str
    inventory_api_url: str
    commerce_vault_addr: str
    commerce_vault_token: str
    identity_vault_addr: str
    identity_vault_token: str
    commerce_token_url: str
    inventory_token_url: str
    inventory_issuer: str
    inventory_client_id: str = "inventory-client"
    compose_network: str
    specmatic_contract_image: str
    specmatic_workflow_image: str
    specmatic_home: Path = Field(default_factory=lambda: Path.home() / ".specmatic")
    container_timeout_seconds: int = 300
    mtls_ca_cert: Path = ROOT / "certs/ca.crt"
    mtls_client_cert: Path = ROOT / "certs/client.crt"
    mtls_client_key: Path = ROOT / "certs/client.key"

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("cert", (str(self.mtls_client_cert), str(self.mtls_client_key)))
        kwargs.setdefault("verify", str(self.mtls_ca_cert))
        kwargs.setdefault("timeout", 10)
        return requests.request(method, url, **kwargs)

    def reset_sample_data(self) -> None:
        seed(reset=True, database_url=self.database_url)

    def run_contract_suite(self, service: str) -> None:
        self.reset_sample_data()
        self._run_specmatic(
            image=self.specmatic_contract_image,
            command="run-suite",
            working_directory=f"/usr/src/app/tests/contract/{service}",
            environment=self._contract_environment(service),
            report_name=service,
        )

    def run_arazzo_workflow(self) -> None:
        self.reset_sample_data()
        self._run_specmatic(
            image=self.specmatic_workflow_image,
            command="test",
            working_directory="/usr/src/app/tests/workflow/arazzo",
            environment={
                "COMMERCE_VAULT_TOKEN": self.commerce_vault_token,
                "IDENTITY_VAULT_TOKEN": self.identity_vault_token,
                "INVENTORY_CLIENT_ID": self.inventory_client_id,
            },
            report_name="arazzo",
            mount_specmatic_home=True,
        )

    def identity_secrets(self) -> dict[str, str]:
        return read_secret(self.identity_vault_addr, self.identity_vault_token, "inventory")

    def _contract_environment(self, service: str) -> dict[str, str]:
        if service == "location":
            commerce = read_secret(self.commerce_vault_addr, self.commerce_vault_token, "commerce")
            return {"LOCATION_BEARER_TOKEN": commerce["location_bearer_token"]}
        if service == "products":
            commerce = read_secret(self.commerce_vault_addr, self.commerce_vault_token, "commerce")
            return {
                "PRODUCTS_READ_TOKEN": self._commerce_token(
                    commerce,
                    scope="products:read",
                    password_grant=True,
                ),
                "PRODUCTS_WRONG_SCOPE_TOKEN": self._commerce_token(
                    commerce,
                    scope="profile",
                    password_grant=True,
                ),
            }
        if service == "orders":
            commerce = read_secret(self.commerce_vault_addr, self.commerce_vault_token, "commerce")
            return {
                "ORDERS_CREATE_TOKEN": self._commerce_token(commerce, scope="orders:create"),
                "ORDERS_READ_TOKEN": self._commerce_token(commerce, scope="orders:read"),
            }
        if service == "inventory":
            identity = self.identity_secrets()
            return {
                "INVENTORY_RESERVE_TOKEN": self._inventory_token(
                    identity,
                    requested_scope="inventory:reserve",
                    grant_scope="inventory:reserve",
                ),
                "INVENTORY_WRONG_SCOPE_TOKEN": self._inventory_token(
                    identity,
                    requested_scope="profile",
                    grant_scope="profile",
                ),
            }
        raise ValueError(f"Unknown contract service: {service}")

    def _commerce_token(self, commerce: dict[str, str], *, scope: str, password_grant: bool = False) -> str:
        if password_grant:
            return commerce_token(
                self.commerce_token_url,
                grant_type="password",
                scope=scope,
                client_id=commerce["products_client_id"],
                username=commerce["products_username"],
                password=commerce["products_password"],
            )
        return commerce_token(
            self.commerce_token_url,
            grant_type="client_credentials",
            scope=scope,
            client_id=commerce["orders_client_id"],
            client_secret=commerce["orders_client_secret"],
        )

    def _inventory_token(
        self,
        identity: dict,
        *,
        requested_scope: str,
        grant_scope: str,
    ) -> str:
        response = post_inventory_token(
            self.inventory_token_url,
            identity,
            client_id=self.inventory_client_id,
            requested_scope=requested_scope,
            grant_scope=grant_scope,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _run_specmatic(
        self,
        *,
        image: str,
        command: str,
        working_directory: str,
        environment: dict[str, str],
        report_name: str,
        mount_specmatic_home: bool = False,
    ) -> None:
        container = (
            DockerContainer(image)
            .with_volume_mapping(str(self.project_root), "/usr/src/app", mode="rw")
            .with_volume_mapping(str(self.project_root / "certs"), "/usr/src/app/certs", mode="ro")
            .with_kwargs(network_mode=self.compose_network, working_dir=working_directory)
            .with_command(command)
            .with_envs(**environment)
        )
        if mount_specmatic_home and self.specmatic_home.is_dir():
            container.with_volume_mapping(str(self.specmatic_home), "/root/.specmatic", mode="ro")

        started = False
        try:
            container.start()
            started = True
            result = container.get_wrapped_container().wait(timeout=self.container_timeout_seconds)
            logs = _container_logs(container)
            _copy_reports(self.project_root, report_name)
            safe_logs = JWT_PATTERN.sub("<redacted JWT>", logs)
            print(safe_logs)
            if result.get("StatusCode", 1) != 0:
                raise AssertionError(f"Specmatic run failed for {report_name}:\n{safe_logs}")
        finally:
            if started:
                container.stop()


def _container_logs(container: DockerContainer) -> str:
    stdout, stderr = container.get_logs()
    return (stdout + stderr).decode(errors="replace")


def _copy_reports(project_root: Path, name: str) -> None:
    if name == "arazzo":
        return

    source = project_root / "tests" / "contract" / name / "build" / "reports" / "specmatic"
    if not source.exists():
        return

    destination = project_root / "build" / "reports" / "specmatic" / name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


test_config = TestConfig()
