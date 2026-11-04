from __future__ import annotations

import time

import requests


def read_kv2(addr: str, token: str, path: str) -> dict:
    last_error: Exception | None = None
    url = f"{addr.rstrip('/')}/v1/secret/data/{path.lstrip('/')}"

    for attempt in range(30):
        try:
            response = requests.get(url, headers={"X-Vault-Token": token}, timeout=3)
            response.raise_for_status()
            return response.json()["data"]["data"]
        except (requests.RequestException, KeyError, ValueError) as error:
            last_error = error
            if attempt < 29:
                time.sleep(1)

    raise RuntimeError(f"Could not read Vault secret at {path}: {last_error}")
