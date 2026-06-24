"""Book setup fields, reference parse metadata, material conflicts JSONB.

Revision ID: i6j7k8l9m0n1
Revises: h5i6j7k8l9m0
Create Date: 2026-06-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i6j7k8l9m0n1"
down_revision: Union[str, None] = "h5i6j7k8l9m0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

outline_usage_enum = postgresql.ENUM("primary", "reference", name="outline_usage", create_type=False)


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    outline_usage_enum.create(conn, checkfirst=True)

    book_cols = {c["name"] for c in insp.get_columns("books")}
    if "original_title" not in book_cols:
        op.add_column("books", sa.Column("original_title", sa.String(length=500), nullable=True))
        op.execute("UPDATE books SET original_title = title WHERE original_title IS NULL")
    if "allow_title_optimization" not in book_cols:
        op.add_column(
            "books",
            sa.Column("allow_title_optimization", sa.Boolean(), nullable=False, server_default="false"),
        )
    if "disciplines" not in book_cols:
        op.add_column("books", sa.Column("disciplines", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        op.execute(
            "UPDATE books SET disciplines = jsonb_build_array(discipline) "
            "WHERE discipline IS NOT NULL AND discipline <> '' AND disciplines IS NULL"
        )
    if "topic_brief" not in book_cols:
        op.add_column("books", sa.Column("topic_brief", sa.Text(), nullable=True))
    if "ai_inferred_settings" not in book_cols:
        op.add_column("books", sa.Column("ai_inferred_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "setup_recommendation_cache" not in book_cols:
        op.add_column(
            "books",
            sa.Column("setup_recommendation_cache", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "narrative_constitution_outline_hash" not in book_cols:
        op.add_column("books", sa.Column("narrative_constitution_outline_hash", sa.String(length=64), nullable=True))
    if "constitution_stale" not in book_cols:
        op.add_column(
            "books",
            sa.Column("constitution_stale", sa.Boolean(), nullable=False, server_default="false"),
        )
    if "material_conflicts" not in book_cols:
        op.add_column("books", sa.Column("material_conflicts", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    ref_cols = {c["name"] for c in insp.get_columns("reference_files")}
    if "file_purposes" not in ref_cols:
        op.add_column("reference_files", sa.Column("file_purposes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "outline_usage" not in ref_cols:
        op.add_column("reference_files", sa.Column("outline_usage", outline_usage_enum, nullable=True))
    if "user_note" not in ref_cols:
        op.add_column("reference_files", sa.Column("user_note", sa.Text(), nullable=True))
    if "parse_version" not in ref_cols:
        op.add_column(
            "reference_files",
            sa.Column("parse_version", sa.Integer(), nullable=False, server_default="0"),
        )
    if "parse_artifacts" not in ref_cols:
        op.add_column(
            "reference_files",
            sa.Column("parse_artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("reference_files", "parse_artifacts")
    op.drop_column("reference_files", "parse_version")
    op.drop_column("reference_files", "user_note")
    op.drop_column("reference_files", "outline_usage")
    op.drop_column("reference_files", "file_purposes")
    op.drop_column("books", "material_conflicts")
    op.drop_column("books", "constitution_stale")
    op.drop_column("books", "narrative_constitution_outline_hash")
    op.drop_column("books", "setup_recommendation_cache")
    op.drop_column("books", "ai_inferred_settings")
    op.drop_column("books", "topic_brief")
    op.drop_column("books", "disciplines")
    op.drop_column("books", "allow_title_optimization")
    op.drop_column("books", "original_title")
    outline_usage_enum.drop(op.get_bind(), checkfirst=True)
