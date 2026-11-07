"""Create non-content app metadata.

Revision ID: 20261015_0001
Revises:
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.String(length=512), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
