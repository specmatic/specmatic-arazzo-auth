from sqlmodel import Field, SQLModel


class UserRow(SQLModel, table=True):
    __tablename__ = "users"

    user_id: int = Field(primary_key=True)
    user_email: str = Field(unique=True, index=True)
    location_code: str


class ProductRow(SQLModel, table=True):
    __tablename__ = "products"

    product_id: int = Field(primary_key=True)
    name: str
    price: float
    location_code: str


class InventoryRow(SQLModel, table=True):
    __tablename__ = "inventory"

    product_id: int = Field(primary_key=True, foreign_key="products.product_id")
    quantity_available: int


class OrderRow(SQLModel, table=True):
    __tablename__ = "orders"

    order_id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id")
    product_id: int = Field(foreign_key="products.product_id")
    inventory: int
    order_request_id: str = Field(index=True)
    status: str = Field(default="PENDING", index=True)


class ReservationRow(SQLModel, table=True):
    __tablename__ = "reservations"

    order_id: int = Field(primary_key=True, foreign_key="orders.order_id")
    product_id: int = Field(foreign_key="products.product_id")
    inventory: int
    status: str = Field(default="reserved", index=True)
