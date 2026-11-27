"""Add shared login limits and one-time email verification state."""

from alembic import op
import sqlalchemy as sa


revision = "0006_security_controls"
down_revision = "0005_user_token_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_login_rate_limit_buckets_window_started_at",
        "login_rate_limit_buckets",
        ["window_started_at"],
    )
    op.create_table(
        "email_change_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("pending_email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_email_change_verifications_expires_at", "email_change_verifications", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_email_change_verifications_expires_at", table_name="email_change_verifications")
    op.drop_table("email_change_verifications")
    op.drop_index("ix_login_rate_limit_buckets_window_started_at", table_name="login_rate_limit_buckets")
    op.drop_table("login_rate_limit_buckets")
