"""Medidas opcionales de prendas y recuperación segura de acceso."""
from alembic import op
import sqlalchemy as sa

revision = "20261116_checkout_recovery"
down_revision = "20261115_product_reviews"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("product_variants")}
    for name in ("bust_cm", "waist_cm", "hip_cm"):
        if name not in columns:
            op.add_column("product_variants", sa.Column(name, sa.Numeric(5, 1), nullable=True))
    if "token_version" not in {column["name"] for column in sa.inspect(bind).get_columns("users")}:
        op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    if "password_reset_tokens" not in sa.inspect(bind).get_table_names():
        op.create_table("password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
    with op.batch_alter_table("product_variants") as batch:
        for name in ("hip_cm", "waist_cm", "bust_cm"):
            batch.drop_column(name)
