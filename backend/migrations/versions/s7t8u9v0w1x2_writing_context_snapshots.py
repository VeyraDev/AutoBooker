"""generation_context_snapshots + nullable intake material source_file_id."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s7t8u9v0w1x2"
down_revision: Union[str, None] = "r1s2t3u4v5w6_refactor_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_context_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("understanding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("writing_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requirement_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("outline_constraint_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("prompt_excerpt", sa.Text, nullable=True),
        sa.Column("source_module", sa.String(32), nullable=False),
        sa.Column("chapter_index", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_generation_context_snapshots_book_id", "generation_context_snapshots", ["book_id"])

    op.alter_column("writing_requirements", "source_file_id", existing_type=postgresql.UUID(), nullable=True)
    op.alter_column("material_terms", "source_file_id", existing_type=postgresql.UUID(), nullable=True)
    op.alter_column("outline_constraints", "source_file_id", existing_type=postgresql.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("outline_constraints", "source_file_id", existing_type=postgresql.UUID(), nullable=False)
    op.alter_column("material_terms", "source_file_id", existing_type=postgresql.UUID(), nullable=False)
    op.alter_column("writing_requirements", "source_file_id", existing_type=postgresql.UUID(), nullable=False)
    op.drop_index("ix_generation_context_snapshots_book_id", table_name="generation_context_snapshots")
    op.drop_table("generation_context_snapshots")
