"""Carga inicial del vestido body de encaje, vino, talla M."""

from alembic import op
import sqlalchemy as sa

revision = "20261111_vestido_body"
down_revision = "20261108_product_gallery"
branch_labels = None
depends_on = None

SLUG = "vestido-body-de-encaje"
PHOTOS = "https://arielloza23.github.io/tienda-web/productos/vestido-body-de-encaje"


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
    # No modifica un producto que ya haya sido cargado o editado por el dueño.
    if connection.execute(sa.select(products.c.id).where(products.c.slug == SLUG)).first():
        return

    connection.execute(products.insert().values(
        name="Vestido body de encaje",
        slug=SLUG,
        description="Body de encaje color vino, talla M.",
        price_cents=1500,
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
        sku="VBE-VINO-M",
        size="M",
        color="Vino",
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
    descriptions = ["Vista frontal", "Vista posterior", "Detalle del encaje"]
    connection.execute(images.insert(), [
        {
            "product_id": product_id,
            "url": f"{PHOTOS}/adicional-{position + 1}.avif",
            "alt": f"Vestido body de encaje vino · {description}",
            "color": "Vino",
            "position": position,
        }
        for position, description in enumerate(descriptions)
    ])


def downgrade() -> None:
    # Conserva el catálogo y las referencias de pedidos al retroceder esta revisión.
    pass
