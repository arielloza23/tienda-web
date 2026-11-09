"""Galería de fotos por producto y color."""

from alembic import op
import sqlalchemy as sa

revision = "20261108_product_gallery"
down_revision = "20261103_product_image_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "product_images" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "product_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("alt", sa.String(200), nullable=False),
        sa.Column("color", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("product_images")
