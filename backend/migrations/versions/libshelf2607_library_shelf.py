"""Add shared bookshelf tables + ensure global_literature exists.

Revision ID: libshelf2607
Revises: libpub202607
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "libshelf2607"
down_revision: Union[str, None] = "libpub202607"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    gl_source = postgresql.ENUM("curated", "community", name="global_literature_source", create_type=False)
    gl_status = postgresql.ENUM("approved", "pending", "rejected", name="global_literature_status", create_type=False)
    item_status = postgresql.ENUM(
        "published", "pending", "archived", "rejected", name="library_item_status", create_type=False
    )

    if "global_literature" not in tables:
        gl_source.create(conn, checkfirst=True)
        gl_status.create(conn, checkfirst=True)
        op.create_table(
            "global_literature",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("source", gl_source, nullable=False),
            sa.Column("status", gl_status, nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("authors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("journal", sa.String(length=300), nullable=True),
            sa.Column("doi", sa.String(length=200), nullable=True),
            sa.Column("url", sa.String(length=1000), nullable=True),
            sa.Column("abstract", sa.Text(), nullable=True),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("contributor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("contributor_name", sa.String(length=120), nullable=True),
            sa.Column("cite_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "library_categories" not in tables:
        op.create_table(
            "library_categories",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("slug"),
        )
        op.create_index("ix_library_categories_slug", "library_categories", ["slug"])

    if "library_items" not in tables:
        item_status.create(conn, checkfirst=True)
        op.create_table(
            "library_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("authors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "category_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("library_categories.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("language", sa.String(length=32), nullable=True),
            sa.Column("file_type", sa.String(length=16), nullable=False),
            sa.Column("filename", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=128), nullable=False),
            sa.Column("content", sa.LargeBinary(), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column(
                "uploader_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("uploader_name", sa.String(length=120), nullable=True),
            sa.Column("status", item_status, nullable=False),
            sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_library_items_title", "library_items", ["title"])
        op.create_index("ix_library_items_category_id", "library_items", ["category_id"])
        op.create_index("ix_library_items_uploader_id", "library_items", ["uploader_id"])
        op.create_index("ix_library_items_status", "library_items", ["status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "library_items" in tables:
        op.drop_table("library_items")
    if "library_categories" in tables:
        op.drop_table("library_categories")
    op.execute("DROP TYPE IF EXISTS library_item_status")
    # keep global_literature if it was created elsewhere
