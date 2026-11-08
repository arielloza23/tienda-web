from alembic import op
import sqlalchemy as sa

revision = "20261101_remove_stock"
down_revision = "20261031_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in ("product_variants", "products"):
        if table_name not in inspector.get_table_names():
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "stock" in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column("stock")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in ("products", "product_variants"):
        if table_name in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "stock" not in columns:
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.add_column(
                        sa.Column("stock", sa.Integer(), server_default="0", nullable=False)
                    )