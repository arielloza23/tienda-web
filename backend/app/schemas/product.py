from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductVariantBase(BaseModel):
    sku: str = Field(..., min_length=3, max_length=100)
    size: Optional[str] = None
    color: Optional[str] = None
    price_adjustment_cents: int = Field(default=0, ge=0)


class ProductVariantCreate(ProductVariantBase):
    model_config = ConfigDict(extra="forbid")


class ProductVariantRead(ProductVariantBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    price_cents: int = Field(..., ge=0)
    is_active: bool = True


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ProductRead(ProductBase):
    id: int
    variants: list[ProductVariantRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
