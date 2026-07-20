"""Add books.publication_info JSONB for export cover metadata.

Revision ID: libpub202607
Revises: f0a1b2c3d4e8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "libpub202607"
down_revision: Union[str, None] = "f0a1b2c3d4e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("publication_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("books", "publication_info")
