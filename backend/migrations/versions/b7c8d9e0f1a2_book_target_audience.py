"""add books.target_audience

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("target_audience", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "target_audience")
