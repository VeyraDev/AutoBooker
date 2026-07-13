"""Assistant domain: writing_bases table and related FK columns."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t8u9v0w1x2y3"
down_revision: Union[str, None] = "s7t8u9v0w1x2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE writing_basis_status AS ENUM ('draft', 'confirmed', 'superseded')"
    )

    op.create_table(
        "writing_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            postgresql.ENUM(name="writing_basis_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("book_promise", sa.Text(), nullable=True),
        sa.Column("target_readers", sa.Text(), nullable=True),
        sa.Column("reader_outcome", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("depth", sa.Text(), nullable=True),
        sa.Column("voice", sa.Text(), nullable=True),
        sa.Column("material_policy", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("outline_policy", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("citation_policy", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("figure_policy", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("must_keep", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("must_avoid", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("open_questions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source_understanding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_writing_bases_book_id", "writing_bases", ["book_id"])
    op.create_index("ix_writing_bases_book_status", "writing_bases", ["book_id", "status"])

    op.add_column(
        "project_intakes",
        sa.Column("confirmed_writing_basis_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.add_column(
        "generation_context_snapshots",
        sa.Column("writing_basis_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_context_snapshots", "writing_basis_id")
    op.drop_column("project_intakes", "confirmed_writing_basis_id")
    op.drop_index("ix_writing_bases_book_status", table_name="writing_bases")
    op.drop_index("ix_writing_bases_book_id", table_name="writing_bases")
    op.drop_table("writing_bases")
    op.execute("DROP TYPE writing_basis_status")
