"""chapter review reports, issues, and applications

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f7
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chapter_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manuscript_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=80), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("markdown_snapshot", sa.Text(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("score_schema_version", sa.String(length=32), nullable=False, server_default="review_v2"),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, server_default="review_agent_v2"),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("constitution_hash", sa.String(length=80), nullable=True),
        sa.Column("citation_index_hash", sa.String(length=80), nullable=True),
        sa.Column("figure_index_hash", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_chapter_reviews_chapter_id", "chapter_reviews", ["chapter_id"])
    op.create_index("ix_chapter_reviews_manuscript_id", "chapter_reviews", ["manuscript_id"])
    op.create_index("ix_chapter_reviews_snapshot_hash", "chapter_reviews", ["snapshot_hash"])

    op.create_table(
        "chapter_review_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapter_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=80), nullable=False),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("penalty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False, server_default="revise"),
        sa.Column("replacement_text", sa.Text(), nullable=True),
        sa.Column("paragraph_id", sa.String(length=80), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("anchor_hash", sa.String(length=80), nullable=True),
        sa.Column("issue_fingerprint", sa.String(length=120), nullable=True),
        sa.Column("detector", sa.String(length=80), nullable=False, server_default="review_agent"),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="0.7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chapter_review_issues_review_id", "chapter_review_issues", ["review_id"])
    op.create_index("ix_chapter_review_issues_chapter_id", "chapter_review_issues", ["chapter_id"])
    op.create_index("ix_chapter_review_issues_snapshot_hash", "chapter_review_issues", ["snapshot_hash"])
    op.create_index("ix_chapter_review_issues_dimension", "chapter_review_issues", ["dimension"])
    op.create_index("ix_chapter_review_issues_issue_type", "chapter_review_issues", ["issue_type"])
    op.create_index("ix_chapter_review_issues_severity", "chapter_review_issues", ["severity"])
    op.create_index("ix_chapter_review_issues_status", "chapter_review_issues", ["status"])
    op.create_index("ix_chapter_review_issues_anchor_hash", "chapter_review_issues", ["anchor_hash"])
    op.create_index("ix_chapter_review_issues_issue_fingerprint", "chapter_review_issues", ["issue_fingerprint"])
    op.create_index("ix_chapter_review_issues_paragraph_id", "chapter_review_issues", ["paragraph_id"])

    op.create_table(
        "review_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapter_review_issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapter_reviews.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("before_hash", sa.String(length=80), nullable=False),
        sa.Column("after_hash", sa.String(length=80), nullable=False),
        sa.Column("apply_type", sa.String(length=32), nullable=False),
        sa.Column("locator_strategy", sa.String(length=64), nullable=True),
        sa.Column("locator_confidence", sa.Numeric(4, 3), nullable=False, server_default="0.0"),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("affected_dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("score_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score_after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_review_applications_issue_id", "review_applications", ["issue_id"])
    op.create_index("ix_review_applications_review_id", "review_applications", ["review_id"])
    op.create_index("ix_review_applications_chapter_id", "review_applications", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_review_applications_chapter_id", table_name="review_applications")
    op.drop_index("ix_review_applications_review_id", table_name="review_applications")
    op.drop_index("ix_review_applications_issue_id", table_name="review_applications")
    op.drop_table("review_applications")

    op.drop_index("ix_chapter_review_issues_paragraph_id", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_issue_fingerprint", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_anchor_hash", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_status", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_severity", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_issue_type", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_dimension", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_snapshot_hash", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_chapter_id", table_name="chapter_review_issues")
    op.drop_index("ix_chapter_review_issues_review_id", table_name="chapter_review_issues")
    op.drop_table("chapter_review_issues")

    op.drop_index("ix_chapter_reviews_snapshot_hash", table_name="chapter_reviews")
    op.drop_index("ix_chapter_reviews_manuscript_id", table_name="chapter_reviews")
    op.drop_index("ix_chapter_reviews_chapter_id", table_name="chapter_reviews")
    op.drop_table("chapter_reviews")
