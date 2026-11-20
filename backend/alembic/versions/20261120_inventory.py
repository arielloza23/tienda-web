"""Stock por variante y reservas manuales; pedidos anteriores sin descuento."""
from alembic import op
import sqlalchemy as sa

revision = "20261120_inventory"
down_revision = "20261116_catalog_products"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in ("products", "product_variants"):
        columns = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if "stock_quantity" not in columns:
            op.add_column(table, sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="1"))
        name = f"ck_{table}_stock_quantity"
        checks = {c["name"] for c in sa.inspect(bind).get_check_constraints(table)}
        if name not in checks:
            with op.batch_alter_table(table) as batch:
                batch.create_check_constraint(name, "stock_quantity >= 0 AND stock_quantity <= 2147483647")
    if "inventory_deducted" not in {c["name"] for c in sa.inspect(bind).get_columns("orders")}:
        op.add_column("orders", sa.Column("inventory_deducted", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    bind = op.get_bind()
    # No perder el significado de reservas al retirar el marcador de inventario.
    if bind.execute(sa.text("SELECT COUNT(*) FROM orders WHERE inventory_deducted = true OR status = 'reserved'")).scalar():
        raise RuntimeError("No se puede retirar inventario mientras existan pedidos con stock descontado o reservado.")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("inventory_deducted")
    for table in ("product_variants", "products"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"ck_{table}_stock_quantity", type_="check")
            batch.drop_column("stock_quantity")
