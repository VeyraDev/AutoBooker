"""book scene-specific ai models

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("outline_ai_model", sa.String(length=80), nullable=True))
    op.add_column("books", sa.Column("constitution_ai_model", sa.String(length=80), nullable=True))
    op.add_column("books", sa.Column("writing_ai_model", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "writing_ai_model")
    op.drop_column("books", "constitution_ai_model")
    op.drop_column("books", "outline_ai_model")
