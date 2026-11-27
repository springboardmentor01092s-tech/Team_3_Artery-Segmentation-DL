"""Add persisted bearer-token versioning for user sessions.

Revision ID: 0005_user_token_version
Revises: 0004_user_management
Create Date: 2026-11-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_user_token_version"
down_revision = "0004_user_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "token_version")
