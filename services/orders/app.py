from __future__ import annotations

from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from common.auth.access_tokens import commerce_auth
from common.db.models import InventoryRow, OrderRow, ProductRow, UserRow
from common.db.session import get_session
from common.http.errors import install_error_handler

app = FastAPI(title="Orders API", version="1.0.0")
install_error_handler(app)


class CreateOrderRequest(BaseModel):
    userId: int = Field(ge=1)
    productId: int = Field(ge=1)
    inventory: int = Field(ge=1)


class CreatedOrder(BaseModel):
    orderId: int


class OrderDetail(BaseModel):
    orderId: int
    userId: int
    productId: int
    inventory: int
    status: str


def render_order(row: OrderRow) -> OrderDetail:
    return OrderDetail(
        orderId=row.order_id,
        userId=row.user_id,
        productId=row.product_id,
        inventory=row.inventory,
        status=row.status,
    )


@app.post("/orders", status_code=201, response_model=CreatedOrder, operation_id="createOrder")
def create_order(
    request: CreateOrderRequest,
    request_id: UUID = Header(..., alias="requestId"),
    _: dict = Depends(commerce_auth("orders-api", "orders:create")),
    session: Session = Depends(get_session),
) -> CreatedOrder:
    user = session.get(UserRow, request.userId)
    if user is None:
        raise HTTPException(status_code=404, detail={"message": "User was not found"})
    product = session.get(ProductRow, request.productId)
    if product is None:
        raise HTTPException(status_code=404, detail={"message": "Product was not found"})
    inventory = session.get(InventoryRow, request.productId)
    if inventory is None or inventory.quantity_available < request.inventory:
        raise HTTPException(status_code=409, detail={"message": "Insufficient inventory is available"})

    order = OrderRow(
        user_id=request.userId,
        product_id=request.productId,
        inventory=request.inventory,
        order_request_id=str(request_id),
        status="PENDING",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return CreatedOrder(orderId=order.order_id)


@app.get("/orders/{orderId}", response_model=OrderDetail, operation_id="getOrderDetail")
def get_order_detail(
    orderId: int,
    _: dict = Depends(commerce_auth("orders-api", "orders:read")),
    session: Session = Depends(get_session),
) -> OrderDetail:
    row = session.get(OrderRow, orderId)
    if row is None:
        raise HTTPException(status_code=404, detail={"message": "Order was not found"})
    return render_order(row)


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
