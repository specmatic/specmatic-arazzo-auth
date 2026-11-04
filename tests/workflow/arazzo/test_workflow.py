from tests.contract.config import test_config


def test_place_order_arazzo_workflow() -> None:
    test_config.run_arazzo_workflow()
