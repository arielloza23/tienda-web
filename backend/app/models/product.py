from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import ProductVariant


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("stock_quantity >= 0 AND stock_quantity <= 2147483647", name="ck_products_stock_quantity"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.position",
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    @property
    def available_stock_quantity(self) -> int:
        return sum(v.stock_quantity for v in self.variants) if self.variants else self.stock_quantity


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt: Mapped[str] = mapped_column(String(200), nullable=False)
    color: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (CheckConstraint("stock_quantity >= 0 AND stock_quantity <= 2147483647", name="ck_product_variants_stock_quantity"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    price_adjustment_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    bust_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1), nullable=True)
    waist_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1), nullable=True)
    hip_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1), nullable=True)

    product: Mapped[Product] = relationship(back_populates="variants")
