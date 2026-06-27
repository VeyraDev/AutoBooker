"""drop book-level ai model columns (use users.*_ai_model)

Revision ID: m0n1p2q3r4s5
Revises: l9m0n1p2q3r4
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m0n1p2q3r4s5"
down_revision: Union[str, None] = "l9m0n1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("books", "writing_ai_model")
    op.drop_column("books", "constitution_ai_model")
    op.drop_column("books", "outline_ai_model")
    op.drop_column("books", "ai_model")


def downgrade() -> None:
    op.add_column("books", sa.Column("ai_model", sa.String(length=80), nullable=True))
    op.add_column("books", sa.Column("outline_ai_model", sa.String(length=80), nullable=True))
    op.add_column("books", sa.Column("constitution_ai_model", sa.String(length=80), nullable=True))
    op.add_column("books", sa.Column("writing_ai_model", sa.String(length=80), nullable=True))
