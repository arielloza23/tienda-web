"""Conserva claves de reintento sin alterar pedidos anteriores."""
from alembic import op
import sqlalchemy as sa

revision = "20261115_order_idempotency"
down_revision = "20261111_conjunto_encaje"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("orders")}
    if "idempotency_key" not in columns:
        op.add_column("orders", sa.Column("idempotency_key", sa.String(36), nullable=True))
    if "request_hash" not in columns:
        op.add_column("orders", sa.Column("request_hash", sa.String(64), nullable=True))
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("orders")}
    if "ix_orders_idempotency_key" not in indexes:
        op.create_index("ix_orders_idempotency_key", "orders", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_orders_idempotency_key", table_name="orders")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("request_hash")
        batch.drop_column("idempotency_key")
