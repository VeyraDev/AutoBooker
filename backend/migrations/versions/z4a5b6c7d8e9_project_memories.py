"""Project memories table (Stage 5)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "z4a5b6c7d8e9"
down_revision: Union[str, None] = "y3z4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE project_memory_type AS ENUM ('fact', 'decision', 'constraint', 'open_question', 'risk')")
    op.execute("CREATE TYPE project_memory_strength AS ENUM ('must', 'should', 'preference')")
    op.create_table(
        "project_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "memory_type",
            postgresql.ENUM(name="project_memory_type", create_type=False),
            nullable=False,
            server_default="fact",
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "source_turn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_turns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "strength",
            postgresql.ENUM(name="project_memory_strength", create_type=False),
            nullable=False,
            server_default="should",
        ),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_project_memories_book_id", "project_memories", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_project_memories_book_id", table_name="project_memories")
    op.drop_table("project_memories")
    op.execute("DROP TYPE IF EXISTS project_memory_strength")
    op.execute("DROP TYPE IF EXISTS project_memory_type")
