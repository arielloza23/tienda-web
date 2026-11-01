from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class OrderItemRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit_price_cents: int
    quantity: int
    total_price_cents: int

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    user_id: int
    shipping_total_cents: int = Field(default=0, ge=0)
    tax_total_cents: int = Field(default=0, ge=0)
    items: list[OrderItemCreate] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class OrderRead(BaseModel):
    id: int
    user_id: int
    status: OrderStatus
    shipping_total_cents: int
    tax_total_cents: int
    subtotal_cents: int
    total_cents: int
    created_at: datetime
    items: list[OrderItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
