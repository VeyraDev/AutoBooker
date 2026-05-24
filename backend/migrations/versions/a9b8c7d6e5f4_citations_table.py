"""citations table for bibliography management

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN CREATE TYPE citation_source AS ENUM "
        "('literature_search', 'uploaded_file', 'manual'); EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doi", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("authors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("journal", sa.String(length=500), nullable=True),
        sa.Column("format_cache", postgresql.JSONB(), nullable=True),
        sa.Column(
            "source",
            postgresql.ENUM(
                "literature_search",
                "uploaded_file",
                "manual",
                name="citation_source",
                create_type=False,
            ),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("list_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_citations_book_id", "citations", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_citations_book_id", table_name="citations")
    op.drop_table("citations")
    op.execute("DROP TYPE IF EXISTS citation_source")
