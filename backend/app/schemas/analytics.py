from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

EventType = Literal["product_view", "variant_select", "gallery_open", "reviews_open", "add_to_cart", "checkout_start", "whatsapp_click", "filter_apply"]
EVENT_TYPES = ("product_view", "variant_select", "gallery_open", "reviews_open", "add_to_cart", "checkout_start", "whatsapp_click", "filter_apply")


class AnalyticsEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    session_id: UUID
    event_type: EventType
    product_id: int | None = Field(default=None, gt=0, le=2147483647, strict=True)
    variant_id: int | None = Field(default=None, gt=0, le=2147483647, strict=True)
    target: Literal["size", "color", "price", "sort", "clear"] | None = None

    @model_validator(mode="after")
    def check_context(self):
        if self.event_type == "filter_apply":
            if self.target is None or self.product_id is not None or self.variant_id is not None:
                raise ValueError("Filtro sin producto, con objetivo permitido.")
        elif self.target is not None or self.product_id is None:
            raise ValueError("La interaccion requiere producto y no admite texto libre.")
        if self.event_type == "variant_select" and self.variant_id is None:
            raise ValueError("Selecciona una variante.")
        return self


class AnalyticsBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[AnalyticsEventCreate] = Field(min_length=1, max_length=20)
