from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    variant_id: Optional[int] = Field(default=None, gt=0)
    quantity: int = Field(..., gt=0)

    model_config = ConfigDict(extra="forbid")


class OrderItemRead(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int]
    product_name: str
    variant_label: Optional[str]
    unit_price_cents: int
    quantity: int
    total_price_cents: int

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    user_id: Optional[int] = Field(default=None, gt=0)
    customer_name: str = Field(..., min_length=2, max_length=200)
    customer_phone: str = Field(..., min_length=7, max_length=30)
    delivery_address: str = Field(..., min_length=8, max_length=500)
    delivery_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    delivery_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    items: list[OrderItemCreate] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_coordinates_pair(self) -> "OrderCreate":
        if (self.delivery_latitude is None) != (self.delivery_longitude is None):
            raise ValueError("Envía latitud y longitud juntas, o ninguna.")
        return self


class OrderRead(BaseModel):
    id: int
    user_id: Optional[int]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    delivery_address: Optional[str]
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    status: OrderStatus
    shipping_total_cents: int
    tax_total_cents: int
    subtotal_cents: int
    total_cents: int
    created_at: datetime
    items: list[OrderItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
