from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.contract.config import test_config

ROOT = Path(__file__).resolve().parents[1]


def run_compose(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        check=True,
        capture_output=capture_output,
        text=True,
    )


@pytest.fixture(scope="session", autouse=True)
def compose_stack() -> Iterator[None]:
    running_services = run_compose("ps", "--status", "running", "--services", capture_output=True).stdout
    pytest_started_stack = not running_services.strip()

    try:
        run_compose(
            "up",
            "--build",
            "--wait",
            "--wait-timeout",
            str(test_config.container_timeout_seconds),
            "-d",
            "location",
            "products",
            "orders",
            "inventory",
        )
        yield
    finally:
        if pytest_started_stack:
            run_compose("down", "--volumes", "--remove-orphans")
