"""Project-level review rule override versions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_rule_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.String(300), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("recommendation", sa.String(24), nullable=False, server_default=""),
        sa.Column("product_dimension", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("issue_type", sa.String(120), nullable=False, server_default="review_issue"),
        sa.Column("fix_capability", sa.String(80), nullable=False, server_default=""),
        sa.Column("detector", sa.String(120), nullable=False, server_default=""),
        sa.Column("rule_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("source_stats_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("book_id", "candidate_id", "version", name="uq_review_rule_override_version"),
    )
    op.create_index("ix_review_rule_overrides_book_id", "review_rule_overrides", ["book_id"])
    op.create_index("ix_review_rule_overrides_candidate_id", "review_rule_overrides", ["candidate_id"])
    op.create_index("ix_review_rule_overrides_status", "review_rule_overrides", ["status"])


def downgrade() -> None:
    op.drop_index("ix_review_rule_overrides_status", table_name="review_rule_overrides")
    op.drop_index("ix_review_rule_overrides_candidate_id", table_name="review_rule_overrides")
    op.drop_index("ix_review_rule_overrides_book_id", table_name="review_rule_overrides")
    op.drop_table("review_rule_overrides")
