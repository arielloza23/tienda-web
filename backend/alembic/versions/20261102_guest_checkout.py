from alembic import op
import sqlalchemy as sa

revision = "20261102_guest_checkout"
down_revision = "20261101_remove_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for temporary_table in ("_alembic_tmp_orders", "_alembic_tmp_order_items"):
        if temporary_table in tables:
            row_count = op.get_bind().execute(
                sa.text(f"SELECT COUNT(*) FROM {temporary_table}")
            ).scalar_one()
            if row_count:
                raise RuntimeError(
                    f"La tabla temporal {temporary_table} contiene datos; no se eliminará automáticamente."
                )
            op.drop_table(temporary_table)
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "orders" in tables:
        columns = {column["name"] for column in inspector.get_columns("orders")}
        with op.batch_alter_table("orders") as batch_op:
            if "user_id" in columns:
                batch_op.alter_column(
                    "user_id",
                    existing_type=sa.Integer(),
                    nullable=True,
                )
            if "customer_name" not in columns:
                batch_op.add_column(sa.Column("customer_name", sa.String(200), nullable=True))
            if "customer_phone" not in columns:
                batch_op.add_column(sa.Column("customer_phone", sa.String(30), nullable=True))
            if "delivery_address" not in columns:
                batch_op.add_column(sa.Column("delivery_address", sa.String(500), nullable=True))

    if "order_items" in tables:
        columns = {column["name"] for column in inspector.get_columns("order_items")}
        with op.batch_alter_table("order_items") as batch_op:
            if "variant_id" not in columns:
                batch_op.add_column(
                    sa.Column(
                        "variant_id",
                        sa.Integer(),
                        sa.ForeignKey(
                            "product_variants.id",
                            name="fk_order_items_variant_id_product_variants",
                        ),
                        nullable=True,
                    )
                )
            if "variant_label" not in columns:
                batch_op.add_column(sa.Column("variant_label", sa.String(200), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    if "orders" in tables:
        guest_orders = connection.execute(
            sa.text("SELECT COUNT(*) FROM orders WHERE user_id IS NULL")
        ).scalar_one()
        if guest_orders:
            raise RuntimeError("No se puede revertir la migración mientras existan pedidos de invitado.")

    if "order_items" in tables:
        columns = {column["name"] for column in sa.inspect(connection).get_columns("order_items")}
        with op.batch_alter_table("order_items") as batch_op:
            if "variant_label" in columns:
                batch_op.drop_column("variant_label")
            if "variant_id" in columns:
                batch_op.drop_column("variant_id")

    if "orders" in tables:
        columns = {column["name"] for column in sa.inspect(connection).get_columns("orders")}
        with op.batch_alter_table("orders") as batch_op:
            for column_name in ("delivery_address", "customer_phone", "customer_name"):
                if column_name in columns:
                    batch_op.drop_column(column_name)
            if "user_id" in columns:
                batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)