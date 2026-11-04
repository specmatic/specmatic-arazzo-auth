from tests.contract.config import test_config


def test_orders_provider_contract() -> None:
    test_config.run_contract_suite("orders")
