"""Carga del conjunto de lencería encaje, blanco, talla M."""

from alembic import op
import sqlalchemy as sa

revision = "20261111_conjunto_encaje"
down_revision = "20261111_vestido_body"
branch_labels = None
depends_on = None

SLUG = "conjunto-de-lenceria-encaje"
PHOTOS = "https://arielloza23.github.io/tienda-web/productos/conjunto-de-lenceria-encaje"


def upgrade() -> None:
    connection = op.get_bind()
    products = sa.table(
        "products",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("description", sa.Text),
        sa.column("price_cents", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("image_url", sa.String),
    )
    if connection.execute(sa.select(products.c.id).where(products.c.slug == SLUG)).first():
        return

    connection.execute(products.insert().values(
        name="Conjunto de lencería encaje",
        slug=SLUG,
        description="Conjunto de lencería de encaje blanco con detalles florales rosados, talla M.",
        price_cents=1200,
        is_active=True,
        image_url=f"{PHOTOS}/portada.avif",
    ))
    product_id = connection.execute(
        sa.select(products.c.id).where(products.c.slug == SLUG)
    ).scalar_one()

    variants = sa.table(
        "product_variants",
        sa.column("product_id", sa.Integer),
        sa.column("sku", sa.String),
        sa.column("size", sa.String),
        sa.column("color", sa.String),
        sa.column("price_adjustment_cents", sa.Integer),
    )
    connection.execute(variants.insert().values(
        product_id=product_id,
        sku="CLE-BLANCO-M",
        size="M",
        color="Blanco",
        price_adjustment_cents=0,
    ))

    images = sa.table(
        "product_images",
        sa.column("product_id", sa.Integer),
        sa.column("url", sa.String),
        sa.column("alt", sa.String),
        sa.column("color", sa.String),
        sa.column("position", sa.Integer),
    )
    descriptions = [
        "Vista frontal del conjunto", "Vista posterior del conjunto",
        "Detalle floral de los tirantes", "Detalle del ajuste del tirante",
    ]
    connection.execute(images.insert(), [
        {
            "product_id": product_id,
            "url": f"{PHOTOS}/adicional-{position + 1}.avif",
            "alt": f"Conjunto de lencería encaje blanco · {description}",
            "color": "Blanco",
            "position": position,
        }
        for position, description in enumerate(descriptions)
    ])


def downgrade() -> None:
    # Conserva los productos y las referencias que puedan tener los pedidos.
    pass
