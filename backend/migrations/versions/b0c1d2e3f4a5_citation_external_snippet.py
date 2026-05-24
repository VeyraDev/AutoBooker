"""citation external source + quotable snippet

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("citations", sa.Column("external_source", sa.String(length=64), nullable=True))
    op.add_column("citations", sa.Column("external_id", sa.String(length=500), nullable=True))
    op.add_column("citations", sa.Column("quotable_snippet", sa.Text(), nullable=True))
    op.create_index(
        "ix_citations_book_external",
        "citations",
        ["book_id", "external_source", "external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_citations_book_external", table_name="citations")
    op.drop_column("citations", "quotable_snippet")
    op.drop_column("citations", "external_id")
    op.drop_column("citations", "external_source")
