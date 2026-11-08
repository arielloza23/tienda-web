"""Esquema inicial (estado del primer commit).

Las bases creadas antes con ``Base.metadata.create_all`` ya tienen estas tablas;
en ese caso la migración no hace nada y solo se registra la revisión.
"""

from alembic import op
import sqlalchemy as sa

revision = "20261031_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(200), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("role", sa.String(30), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "products" not in tables:
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("price_cents", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
        )
        op.create_index("ix_products_id", "products", ["id"])
        op.create_index("ix_products_slug", "products", ["slug"], unique=True)

    if "product_variants" not in tables:
        op.create_table(
            "product_variants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("sku", sa.String(100), nullable=False),
            sa.Column("size", sa.String(50), nullable=True),
            sa.Column("color", sa.String(50), nullable=True),
            sa.Column("price_adjustment_cents", sa.Integer(), nullable=False),
        )
        op.create_index("ix_product_variants_id", "product_variants", ["id"])
        op.create_index("ix_product_variants_sku", "product_variants", ["sku"], unique=True)

    if "orders" not in tables:
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("subtotal_cents", sa.Integer(), nullable=False),
            sa.Column("shipping_total_cents", sa.Integer(), nullable=False),
            sa.Column("tax_total_cents", sa.Integer(), nullable=False),
            sa.Column("total_cents", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_orders_id", "orders", ["id"])

    if "order_items" not in tables:
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("unit_price_cents", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("total_price_cents", sa.Integer(), nullable=False),
        )
        op.create_index("ix_order_items_id", "order_items", ["id"])


def downgrade() -> None:
    for table_name in ("order_items", "orders", "product_variants", "products", "users"):
        op.drop_table(table_name)
