"""pgvector extension + reference_files, reference_chunks, book_memory

Revision ID: a1b2c3d4e5f6
Revises: 07368f58054b
Create Date: 2026-05-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "07368f58054b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "reference_files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("book_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("storage_path", sa.String(length=2000), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column(
            "parse_status",
            sa.Enum("pending", "processing", "done", "failed", name="parse_status"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reference_files_book_id"), "reference_files", ["book_id"], unique=False)

    op.create_table(
        "reference_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("book_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["reference_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reference_chunks_book_id"), "reference_chunks", ["book_id"], unique=False)
    op.create_index(op.f("ix_reference_chunks_file_id"), "reference_chunks", ["file_id"], unique=False)

    op.create_table(
        "book_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("book_id", sa.UUID(), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("style", "term", "summary", "citation", name="memory_type"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=500), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_book_memory_book_id"), "book_memory", ["book_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_book_memory_book_id"), table_name="book_memory")
    op.drop_table("book_memory")
    op.execute(sa.text("DROP TYPE IF EXISTS memory_type"))

    op.drop_index(op.f("ix_reference_chunks_file_id"), table_name="reference_chunks")
    op.drop_index(op.f("ix_reference_chunks_book_id"), table_name="reference_chunks")
    op.drop_table("reference_chunks")

    op.drop_index(op.f("ix_reference_files_book_id"), table_name="reference_files")
    op.drop_table("reference_files")
    op.execute(sa.text("DROP TYPE IF EXISTS parse_status"))
