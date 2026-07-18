"""Citation verification background jobs."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "citation_verification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("requested_citation_ids", postgresql.JSONB(), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_citation_verification_jobs_book_id", "citation_verification_jobs", ["book_id"])
    op.create_index("ix_citation_verification_jobs_user_id", "citation_verification_jobs", ["user_id"])
    op.create_index("ix_citation_verification_jobs_status", "citation_verification_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_citation_verification_jobs_status", table_name="citation_verification_jobs")
    op.drop_index("ix_citation_verification_jobs_user_id", table_name="citation_verification_jobs")
    op.drop_index("ix_citation_verification_jobs_book_id", table_name="citation_verification_jobs")
    op.drop_table("citation_verification_jobs")
