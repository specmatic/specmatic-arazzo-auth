from __future__ import annotations

import subprocess

import pytest
import requests

from tests.contract.config import test_config

API_URLS = [
    pytest.param(test_config.location_api_url, id="location"),
    pytest.param(test_config.products_api_url, id="products"),
    pytest.param(test_config.orders_api_url, id="orders"),
    pytest.param(test_config.inventory_api_url, id="inventory"),
]


@pytest.fixture(scope="module")
def untrusted_client_certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    cert_dir = tmp_path_factory.mktemp("untrusted-client")
    cert_path = cert_dir / "client.crt"
    key_path = cert_dir / "client.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "1",
            "-subj",
            "/CN=untrusted-specmatic-arazzo-auth-client",
            "-addext",
            "basicConstraints=critical,CA:FALSE",
            "-addext",
            "keyUsage=critical,digitalSignature",
            "-addext",
            "extendedKeyUsage=clientAuth",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(cert_path), str(key_path)


@pytest.mark.parametrize("api_url", API_URLS)
def test_health_endpoint_accepts_trusted_client_certificate(api_url: str) -> None:
    response = test_config.request("GET", f"{api_url}/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("api_url", API_URLS)
def test_health_endpoint_rejects_missing_client_certificate(api_url: str) -> None:
    with pytest.raises((requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
        requests.get(
            f"{api_url}/healthz",
            verify=str(test_config.mtls_ca_cert),
            timeout=5,
        )


@pytest.mark.parametrize("api_url", API_URLS)
def test_health_endpoint_rejects_untrusted_client_certificate(
    api_url: str,
    untrusted_client_certificate: tuple[str, str],
) -> None:
    with pytest.raises((requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
        requests.get(
            f"{api_url}/healthz",
            cert=untrusted_client_certificate,
            verify=str(test_config.mtls_ca_cert),
            timeout=5,
        )


@pytest.mark.parametrize("api_url", API_URLS)
def test_api_port_does_not_accept_plain_http(api_url: str) -> None:
    http_url = api_url.replace("https://", "http://", 1)

    with pytest.raises(requests.exceptions.RequestException):
        requests.get(f"{http_url}/healthz", timeout=5)
