"""Reseñas por usuario y producto, sin modificar compras anteriores."""
from alembic import op
import sqlalchemy as sa

revision = "20261115_product_reviews"
down_revision = "20261115_order_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "product_reviews" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "product_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("product_id", "user_id", name="uq_product_reviews_product_user"),
            sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_product_reviews_rating"),
        )
        op.create_index("ix_product_reviews_product_created_id", "product_reviews", ["product_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_product_reviews_product_created_id", table_name="product_reviews")
    op.drop_table("product_reviews")
