from __future__ import annotations

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from common.auth.access_tokens import commerce_auth
from common.db.models import InventoryRow, ProductRow
from common.db.session import get_session
from common.http.errors import install_error_handler

app = FastAPI(title="Products API", version="1.0.0")
install_error_handler(app)


class Product(BaseModel):
    productId: int
    name: str
    price: float
    inventory: int


@app.get("/products", response_model=list[Product], operation_id="getProducts")
def get_products(
    location_code: str = Query(..., alias="locationCode", min_length=1),
    _: dict = Depends(commerce_auth("products-api", "products:read")),
    session: Session = Depends(get_session),
) -> list[Product]:
    statement = (
        select(ProductRow, InventoryRow)
        .join(InventoryRow, InventoryRow.product_id == ProductRow.product_id)
        .where(ProductRow.location_code == location_code)
        .order_by(ProductRow.product_id)
    )
    return [
        Product(
            productId=product.product_id,
            name=product.name,
            price=product.price,
            inventory=inventory.quantity_available,
        )
        for product, inventory in session.exec(statement).all()
    ]


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
