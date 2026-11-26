"""Create application tables absent from legacy or fresh schemas.

Revision ID: 0004
Revises: 0003
"""

from typing import Sequence, Union

from alembic import op

from app import models  # noqa: F401 - registers every application table
from app.database.base import Base

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_all(checkfirst=True) only creates missing tables; it does not drop
    # or rewrite existing tables/rows. This fills tables skipped by older
    # conditional revisions on a fresh or partially initialized database.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # This is an additive compatibility revision. Automatically dropping
    # tables could destroy application data, so downgrade is intentionally a
    # no-op; deployments should use a deliberate, reviewed migration instead.
    pass
