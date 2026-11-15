from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductVariantBase(BaseModel):
    sku: str = Field(..., min_length=3, max_length=100)
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    price_adjustment_cents: int = Field(default=0, ge=0, le=2147483647, strict=True)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProductVariantCreate(ProductVariantBase):
    model_config = ConfigDict(extra="forbid")


class ProductVariantUpdate(ProductVariantCreate):
    id: int | None = Field(default=None, strict=True, gt=0)


class ProductVariantRead(ProductVariantBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: Optional[str] = Field(default=None, max_length=5000)
    price_cents: int = Field(..., ge=0, le=2147483647, strict=True)
    is_active: bool = True

    model_config = ConfigDict(str_strip_whitespace=True)
    image_url: Optional[str] = Field(default=None, max_length=500, pattern=r"^https://\S+$")


class ProductImageCreate(BaseModel):
    url: str = Field(max_length=500, pattern=r"^https://\S+$")
    alt: str = Field(min_length=2, max_length=200)
    color: str = Field(min_length=1, max_length=50)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductImageRead(ProductImageCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = Field(default_factory=list, max_length=100)
    images: list[ProductImageCreate] = Field(default_factory=list, max_length=12)

    model_config = ConfigDict(extra="forbid")


class ProductUpdate(ProductBase):
    variants: list[ProductVariantUpdate] = Field(max_length=100)
    images: list[ProductImageCreate] = Field(max_length=12)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def unique_variant_ids(self):
        ids = [variant.id for variant in self.variants if variant.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas el ID de una variante.")
        return self


class ProductRead(ProductBase):
    id: int
    variants: list[ProductVariantRead] = Field(default_factory=list)
    images: list[ProductImageRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
