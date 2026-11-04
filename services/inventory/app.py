from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from sqlmodel import Session, select

from common.auth.access_tokens import inventory_auth
from common.db.models import InventoryRow, OrderRow, ProductRow, ReservationRow
from common.db.session import get_session
from common.http.errors import install_error_handler

app = FastAPI(title="Inventory API", version="1.0.0")
install_error_handler(app)


@app.put("/inventory", status_code=200, operation_id="reserveInventory")
def reserve_inventory(
    order_id: int = Query(..., alias="orderId", ge=1),
    _: dict = Depends(inventory_auth("inventory:reserve")),
    session: Session = Depends(get_session),
) -> Response:
    order = session.exec(select(OrderRow).where(OrderRow.order_id == order_id).with_for_update()).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"message": "Order was not found"})
    if order.status != "PENDING":
        raise HTTPException(status_code=409, detail={"message": "Order is not pending"})
    product = session.get(ProductRow, order.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail={"message": "Product was not found"})

    inventory = session.exec(
        select(InventoryRow).where(InventoryRow.product_id == order.product_id).with_for_update()
    ).first()
    if inventory is None:
        raise HTTPException(status_code=404, detail={"message": "Inventory was not found"})
    if inventory.quantity_available < order.inventory:
        raise HTTPException(status_code=409, detail={"message": "Insufficient inventory is available"})

    inventory.quantity_available -= order.inventory
    order.status = "ACCEPTED"
    reservation = ReservationRow(
        order_id=order.order_id,
        product_id=order.product_id,
        inventory=order.inventory,
        status="reserved",
    )
    session.add(inventory)
    session.add(order)
    session.add(reservation)
    session.commit()
    return Response(status_code=200)


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
