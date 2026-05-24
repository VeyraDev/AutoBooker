"""book style_type topic_tags user_material; reference_files.ingest_kind

Revision ID: c4d5e6f7a8b9
Revises: b7c8d9e0f1a2
Create Date: 2026-05-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("style_type", sa.String(length=50), nullable=True))
    op.add_column(
        "books",
        sa.Column("topic_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("books", sa.Column("user_material", sa.Text(), nullable=True))
    op.add_column(
        "reference_files",
        sa.Column("ingest_kind", sa.String(length=20), nullable=False, server_default="reference"),
    )


def downgrade() -> None:
    op.drop_column("reference_files", "ingest_kind")
    op.drop_column("books", "user_material")
    op.drop_column("books", "topic_tags")
    op.drop_column("books", "style_type")
