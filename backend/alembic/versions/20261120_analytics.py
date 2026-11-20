"""Analitica propia sin datos personales ni fechas historicas inventadas."""
from alembic import op
import sqlalchemy as sa

revision = "20261120_analytics"
down_revision = "20261120_inventory"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "analytics_events" not in sa.inspect(bind).get_table_names():
        op.create_table("analytics_events",
            sa.Column("event_id", sa.String(36), primary_key=True),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("event_type", sa.String(30), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
            sa.Column("variant_id", sa.Integer(), sa.ForeignKey("product_variants.id", ondelete="SET NULL")),
            sa.Column("target", sa.String(10)),
            sa.Column("created_at", sa.DateTime(), nullable=False))
        op.create_index("ix_analytics_events_created_type", "analytics_events", ["created_at", "event_type"])
        op.create_index("ix_analytics_events_product_session", "analytics_events", ["product_id", "session_id", "created_at"])
    columns = {c["name"] for c in sa.inspect(bind).get_columns("orders")}
    if "analytics_session_id" not in columns:
        op.add_column("orders", sa.Column("analytics_session_id", sa.String(36), nullable=True))
        op.create_index("ix_orders_analytics_session_id", "orders", ["analytics_session_id"])


def downgrade():
    op.drop_index("ix_orders_analytics_session_id", table_name="orders")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("analytics_session_id")
    op.drop_table("analytics_events")
