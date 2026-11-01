from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.order import OrderStatus
from app.schemas.order import OrderCreate, OrderRead
from app.services.order_service import create_order, get_order_by_id, get_orders, update_order_status

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderRead])
def list_orders(db: Session = Depends(get_db)) -> list[OrderRead]:
    return get_orders(db)


@router.get("/{order_id}", response_model=OrderRead)
def read_order(order_id: int, db: Session = Depends(get_db)) -> OrderRead:
    order = get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
    return order


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_new_order(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderRead:
    try:
        return create_order(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_status(order_id: int, new_status: OrderStatus, db: Session = Depends(get_db)) -> OrderRead:
    try:
        return update_order_status(db, order_id, new_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
