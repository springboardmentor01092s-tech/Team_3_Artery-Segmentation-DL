"""case access grants

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "cases" not in tables or "case_access" in tables:
        return
    op.create_table(
        "case_access",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("access_type", sa.String(length=32), nullable=False),
        sa.Column("granted_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_access_case_user"),
    )
    op.create_index("ix_case_access_case_id", "case_access", ["case_id"])
    op.create_index("ix_case_access_user_id", "case_access", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "case_access" not in inspector.get_table_names():
        return
    op.drop_index("ix_case_access_user_id", table_name="case_access")
    op.drop_index("ix_case_access_case_id", table_name="case_access")
    op.drop_table("case_access")
