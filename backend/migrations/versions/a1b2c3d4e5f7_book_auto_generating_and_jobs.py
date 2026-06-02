"""book_status.auto_generating + book_jobs 表

Revision ID: a1b2c3d4e5f7
Revises: f2a3b4c5d6e7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_value_exists(enum_name: str, value: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = :enum_name AND e.enumlabel = :value
            LIMIT 1
            """
        ),
        {"enum_name": enum_name, "value": value},
    ).scalar()
    return row is not None


def upgrade() -> None:
    if not _enum_value_exists("book_status", "auto_generating"):
        op.execute("ALTER TYPE book_status ADD VALUE 'auto_generating' AFTER 'outline_ready'")

    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("book_jobs"):
        book_job_status = postgresql.ENUM(
            "pending",
            "running",
            "completed",
            "failed",
            "cancelled",
            name="book_job_status",
            create_type=False,
        )
        book_job_step = postgresql.ENUM(
            "setting",
            "narrative",
            "literature",
            "outline",
            "preface",
            "writing",
            "bibliography",
            "done",
            name="book_job_step",
            create_type=False,
        )
        book_job_status.create(bind, checkfirst=True)
        book_job_step.create(bind, checkfirst=True)

        op.create_table(
            "book_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", book_job_status, nullable=False, server_default="pending"),
            sa.Column("current_step", book_job_step, nullable=True),
            sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("checkpoint_json", postgresql.JSONB(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_book_jobs_book_id", "book_jobs", ["book_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("book_jobs"):
        op.drop_index("ix_book_jobs_book_id", table_name="book_jobs")
        op.drop_table("book_jobs")
    op.execute("DROP TYPE IF EXISTS book_job_step")
    op.execute("DROP TYPE IF EXISTS book_job_status")
    # PostgreSQL 不支持从 enum 删除单个值，auto_generating 保留
