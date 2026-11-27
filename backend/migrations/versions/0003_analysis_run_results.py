"""Add persisted synchronous analysis run metadata.

Revision ID: 0003_analysis_run_results
Revises: 0002_image_preprocessing
Create Date: 2026-11-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_analysis_run_results"
down_revision = "0002_image_preprocessing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("image_id", sa.Uuid(), nullable=True))
    op.add_column("analysis_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("duration_seconds", sa.Float(), nullable=True))
    op.add_column("analysis_runs", sa.Column("result_metadata", sa.JSON(), nullable=True))
    op.add_column("analysis_runs", sa.Column("failure_code", sa.String(length=50), nullable=True))
    op.add_column("analysis_runs", sa.Column("failure_message", sa.String(length=500), nullable=True))
    op.create_index("ix_analysis_runs_image_id", "analysis_runs", ["image_id"])
    op.create_foreign_key(
        "fk_analysis_runs_image_id_medical_images",
        "analysis_runs",
        "medical_images",
        ["image_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_analysis_runs_image_id_medical_images", "analysis_runs", type_="foreignkey")
    op.drop_index("ix_analysis_runs_image_id", table_name="analysis_runs")
    op.drop_column("analysis_runs", "failure_message")
    op.drop_column("analysis_runs", "failure_code")
    op.drop_column("analysis_runs", "result_metadata")
    op.drop_column("analysis_runs", "duration_seconds")
    op.drop_column("analysis_runs", "started_at")
    op.drop_column("analysis_runs", "image_id")
