from __future__ import annotations

import argparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, delete

from common.db.models import InventoryRow, OrderRow, ProductRow, ReservationRow, UserRow
from common.db.session import engine


def migrate_legacy_schema(database_engine: Engine) -> None:
    expected_columns = {
        "users": {"user_id", "user_email", "location_code"},
        "products": {"product_id", "name", "price", "location_code"},
        "inventory": {"product_id", "quantity_available"},
        "orders": {"order_id", "user_id", "product_id", "inventory", "order_request_id", "status"},
        "reservations": {"order_id", "product_id", "inventory", "status"},
    }
    inspector = inspect(database_engine)
    tables = set(inspector.get_table_names())
    app_tables = tables.intersection({*expected_columns, "locations"})
    if not app_tables:
        return

    schema_is_current = all(
        table in tables and expected.issubset({column["name"] for column in inspector.get_columns(table)})
        for table, expected in expected_columns.items()
    )
    if schema_is_current and "locations" not in tables:
        return

    with database_engine.begin() as connection:
        connection.execute(
            text("DROP TABLE IF EXISTS reservations, orders, inventory, products, locations, users CASCADE")
        )


def seed(reset: bool = False, *, database_url: str | None = None) -> None:
    database_engine = create_engine(database_url, pool_pre_ping=True) if database_url else engine
    try:
        migrate_legacy_schema(database_engine)
        SQLModel.metadata.create_all(database_engine)
        with Session(database_engine) as session:
            if reset:
                for model in (ReservationRow, OrderRow, InventoryRow, ProductRow, UserRow):
                    session.exec(delete(model))
                session.commit()

            session.merge(UserRow(user_id=1, user_email="blr@specmatic.io", location_code="IND-BLR"))
            session.merge(UserRow(user_id=2, user_email="del@specmatic.io", location_code="IND-DEL"))
            session.merge(ProductRow(product_id=1, name="Phone", price=999.0, location_code="IND-BLR"))
            session.merge(ProductRow(product_id=2, name="TWS", price=499.0, location_code="IND-BLR"))
            session.commit()

            for product_id, quantity in ((1, 500), (2, 1000)):
                row = session.get(InventoryRow, product_id)
                if row is None:
                    session.add(InventoryRow(product_id=product_id, quantity_available=quantity))
                elif reset:
                    row.quantity_available = quantity
                    session.add(row)
            session.commit()

            seed_orders = (
                OrderRow(
                    order_id=9001,
                    user_id=1,
                    product_id=1,
                    inventory=500,
                    order_request_id="00000000-0000-4000-8000-000000000001",
                    status="PENDING",
                ),
                OrderRow(
                    order_id=9002,
                    user_id=1,
                    product_id=2,
                    inventory=1,
                    order_request_id="00000000-0000-4000-8000-000000000002",
                    status="ACCEPTED",
                ),
                OrderRow(
                    order_id=9003,
                    user_id=1,
                    product_id=2,
                    inventory=1000,
                    order_request_id="00000000-0000-4000-8000-000000000003",
                    status="PENDING",
                ),
            )
            for order in seed_orders:
                if session.get(OrderRow, order.order_id) is None:
                    session.add(order)
            session.commit()
    finally:
        if database_url is not None:
            database_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Restore the sample data and inventory levels")
    arguments = parser.parse_args()
    seed(reset=arguments.reset)
    print("Seeded users, products, inventory, and order fixtures.")
