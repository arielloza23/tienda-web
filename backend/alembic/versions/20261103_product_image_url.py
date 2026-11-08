"""Imagen por producto (antes estaba fija en el frontend)."""

from alembic import op
import sqlalchemy as sa

revision = "20261103_product_image_url"
down_revision = "20261102_delivery_coordinates"
branch_labels = None
depends_on = None

# Imágenes que el frontend tenía fijas por slug; se copian a la base de datos.
INITIAL_IMAGES = {
    "top-corse-encaje-negro": "https://images.pexels.com/photos/33114806/pexels-photo-33114806.jpeg?auto=compress&cs=tinysrgb&w=900",
    "top-corse-encaje-vino": "https://images.pexels.com/photos/29474759/pexels-photo-29474759.jpeg?auto=compress&cs=tinysrgb&w=900",
    "conjunto-floral-encaje-negro": "https://images.unsplash.com/photo-1652859921634-d30457cb9695?auto=format&fit=crop&w=1200&q=85",
    "conjunto-floral-encaje-vino": "https://images.pexels.com/photos/838787/pexels-photo-838787.jpeg?auto=compress&cs=tinysrgb&w=900",
}


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "products" not in inspector.get_table_names():
        return
    if "image_url" not in {column["name"] for column in inspector.get_columns("products")}:
        with op.batch_alter_table("products") as batch_op:
            batch_op.add_column(sa.Column("image_url", sa.String(500), nullable=True))

    for slug, url in INITIAL_IMAGES.items():
        connection.execute(
            sa.text("UPDATE products SET image_url = :url WHERE slug = :slug AND image_url IS NULL"),
            {"url": url, "slug": slug},
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "products" not in inspector.get_table_names():
        return
    if "image_url" in {column["name"] for column in inspector.get_columns("products")}:
        with op.batch_alter_table("products") as batch_op:
            batch_op.drop_column("image_url")
