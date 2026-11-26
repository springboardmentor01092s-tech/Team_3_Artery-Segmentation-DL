"""Additive segmentation analysis history."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    # The original app initializes the complete schema with SQLAlchemy create_all.
    # This migration is also safe for fresh databases where startup has not yet run.
    if "stenosis_analyses" in tables or not {"cases", "uploaded_images", "users"}.issubset(tables):
        return
    op.create_table(
        "stenosis_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_id", sa.String(36), sa.ForeignKey("uploaded_images.id"), nullable=False),
        sa.Column("initiated_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("model_architecture", sa.String(80)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("artifacts_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_stenosis_analyses_case_id", "stenosis_analyses", ["case_id"])
    op.create_index("ix_stenosis_analyses_image_id", "stenosis_analyses", ["image_id"])


def downgrade() -> None:
    if "stenosis_analyses" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_stenosis_analyses_image_id", table_name="stenosis_analyses")
    op.drop_index("ix_stenosis_analyses_case_id", table_name="stenosis_analyses")
    op.drop_table("stenosis_analyses")
