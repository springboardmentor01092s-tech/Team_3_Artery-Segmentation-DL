"""Persist per-image preprocessing status and metadata.

Revision ID: 0002_image_preprocessing
Revises: 0001_initial
Create Date: 2026-10-25
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_image_preprocessing"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_preprocessing",
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("preprocessed_by_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("result_metadata", sa.JSON(), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('completed', 'failed')", name="ck_image_preprocessing_status"),
        sa.CheckConstraint("attempt_count >= 1", name="ck_image_preprocessing_attempt_count"),
        sa.ForeignKeyConstraint(["image_id"], ["medical_images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["preprocessed_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("image_id"),
    )
    op.create_index("ix_image_preprocessing_preprocessed_by_id", "image_preprocessing", ["preprocessed_by_id"])


def downgrade() -> None:
    op.drop_index("ix_image_preprocessing_preprocessed_by_id", table_name="image_preprocessing")
    op.drop_table("image_preprocessing")
