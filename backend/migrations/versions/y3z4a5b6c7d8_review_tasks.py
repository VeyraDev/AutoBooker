"""Review tasks table (Stage 4 Pass 2)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "y3z4a5b6c7d8"
down_revision: Union[str, None] = "x2y3z4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE review_task_scope AS ENUM ('book', 'chapter', 'custom')")
    op.execute("CREATE TYPE review_task_goal AS ENUM ('default', 'custom')")
    op.execute("CREATE TYPE review_task_status AS ENUM ('pending', 'running', 'completed', 'failed')")
    op.create_table(
        "review_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope",
            postgresql.ENUM(name="review_task_scope", create_type=False),
            nullable=False,
            server_default="book",
        ),
        sa.Column("chapter_indexes", postgresql.JSONB(), nullable=True),
        sa.Column(
            "goal",
            postgresql.ENUM(name="review_task_goal", create_type=False),
            nullable=False,
            server_default="default",
        ),
        sa.Column("custom_prompt", sa.Text(), nullable=True),
        sa.Column("adopted_standards", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("exclusions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("output_threshold", sa.String(32), nullable=False, server_default="all_tiers"),
        sa.Column(
            "status",
            postgresql.ENUM(name="review_task_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("context_snapshot_hash", sa.String(80), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("book_review_stage_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_tasks_book_id", "review_tasks", ["book_id"])
    op.create_index("ix_review_tasks_run_id", "review_tasks", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_review_tasks_run_id", table_name="review_tasks")
    op.drop_index("ix_review_tasks_book_id", table_name="review_tasks")
    op.drop_table("review_tasks")
    op.execute("DROP TYPE review_task_status")
    op.execute("DROP TYPE review_task_goal")
    op.execute("DROP TYPE review_task_scope")
