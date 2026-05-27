"""citation abstract_preview + book last_literature_query

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("citations", sa.Column("abstract_preview", sa.Text(), nullable=True))
    op.add_column("citations", sa.Column("url", sa.String(length=2000), nullable=True))
    op.add_column(
        "books",
        sa.Column("last_literature_query", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("books", "last_literature_query")
    op.drop_column("citations", "url")
    op.drop_column("citations", "abstract_preview")
