"""Carga de cinco productos sin modificar ediciones administrativas."""
from alembic import op
import sqlalchemy as sa

revision = "20261116_catalog_products"
down_revision = "20261116_checkout_recovery"
branch_labels = None
depends_on = None

BASE_URL = "https://arielloza23.github.io/tienda-web/productos"
CATALOG = (
    ("Body de encaje transparente negro", "body-de-encaje-transparente-negro", 804, "Negro", "BET-NEGRO-M", 3),
    ("Conjunto 6 piezas", "conjunto-6-piezas", 3696, "Multicolor", "C6-MULTI-M", 4),
    ("Conjunto de lencería encaje 3 piezas", "conjunto-de-lenceria-encaje-3-piezas", 1040, "Negro", "CLE3-NEGRO-M", 4),
    ("Conjunto de lencería encaje 3 rojo", "conjunto-de-lenceria-encaje-3-rojo", 1518, "Rojo", "CLE3-ROJO-M", 5),
    ("Conjunto de navidad", "conjunto-de-navidad", 1724, "Rojo", "NAV-ROJO-M", 3),
)


def upgrade() -> None:
    connection = op.get_bind()
    products = sa.table("products", sa.column("id", sa.Integer),
        sa.column("name", sa.String), sa.column("slug", sa.String),
        sa.column("description", sa.Text), sa.column("price_cents", sa.Integer),
        sa.column("is_active", sa.Boolean), sa.column("image_url", sa.String))
    variants = sa.table("product_variants", sa.column("product_id", sa.Integer),
        sa.column("sku", sa.String), sa.column("size", sa.String),
        sa.column("color", sa.String), sa.column("price_adjustment_cents", sa.Integer))
    images = sa.table("product_images", sa.column("product_id", sa.Integer),
        sa.column("url", sa.String), sa.column("alt", sa.String),
        sa.column("color", sa.String), sa.column("position", sa.Integer))
    for name, slug, price, color, sku, image_count in CATALOG:
        existing = connection.execute(sa.select(products.c.id).where(products.c.slug == slug)).scalar_one_or_none()
        if existing is not None:
            continue
        connection.execute(products.insert().values(name=name, slug=slug,
            description=f"{name}, talla M.", price_cents=price, is_active=True,
            image_url=f"{BASE_URL}/{slug}/portada.avif"))
        product_id = connection.execute(sa.select(products.c.id).where(products.c.slug == slug)).scalar_one()
        connection.execute(variants.insert().values(product_id=product_id, sku=sku,
            size="M", color=color, price_adjustment_cents=0))
        connection.execute(images.insert(), [
            {"product_id": product_id, "url": f"{BASE_URL}/{slug}/adicional-{position}.avif",
             "alt": f"{name}, vista adicional {position}", "color": color, "position": position}
            for position in range(1, image_count + 1)
        ])


def downgrade() -> None:
    # Conservar productos, ediciones y referencias de pedidos.
    pass