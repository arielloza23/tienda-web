"""Coordenadas opcionales de entrega (para el mapa del checkout)."""

from alembic import op
import sqlalchemy as sa

revision = "20261102_delivery_coordinates"
down_revision = "20261102_guest_checkout"
branch_labels = None
depends_on = None

COLUMNS = ("delivery_latitude", "delivery_longitude")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "orders" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("orders")}
    with op.batch_alter_table("orders") as batch_op:
        for column_name in COLUMNS:
            if column_name not in existing:
                batch_op.add_column(sa.Column(column_name, sa.Float(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "orders" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("orders")}
    with op.batch_alter_table("orders") as batch_op:
        for column_name in reversed(COLUMNS):
            if column_name in existing:
                batch_op.drop_column(column_name)
