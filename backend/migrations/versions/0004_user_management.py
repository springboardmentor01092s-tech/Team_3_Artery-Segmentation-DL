"""Add user names and forced temporary-password changes.

Revision ID: 0004_user_management
Revises: 0003_analysis_run_results
Create Date: 2026-11-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_user_management"
down_revision = "0003_analysis_run_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=120), nullable=True))
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "full_name")
