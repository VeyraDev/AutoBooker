"""notifications + feedback tables

Revision ID: n1o2p3q4r5s6
Revises: m0n1p2q3r4s5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n1o2p3q4r5s6"
down_revision: Union[str, None] = "m0n1p2q3r4s5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    notification_type = postgresql.ENUM("system", "book_job", "feedback_reply", name="notification_type", create_type=False)
    feedback_type = postgresql.ENUM("bug", "feature", "experience", "other", name="feedback_type", create_type=False)
    feedback_status = postgresql.ENUM("open", "replied", "closed", name="feedback_status", create_type=False)

    notification_type.create(bind, checkfirst=True)
    feedback_type.create(bind, checkfirst=True)
    feedback_status.create(bind, checkfirst=True)

    if not insp.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("type", notification_type, nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("payload_json", postgresql.JSONB(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    if not insp.has_table("feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("type", feedback_type, nullable=False),
            sa.Column("status", feedback_status, nullable=False, server_default="open"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("page_url", sa.String(500), nullable=True),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
            sa.Column("meta_json", postgresql.JSONB(), nullable=True),
            sa.Column("reply", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_feedback_user_id", "feedback", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("feedback"):
        op.drop_index("ix_feedback_user_id", table_name="feedback")
        op.drop_table("feedback")
    if insp.has_table("notifications"):
        op.drop_index("ix_notifications_user_id", table_name="notifications")
        op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS feedback_status")
    op.execute("DROP TYPE IF EXISTS feedback_type")
    op.execute("DROP TYPE IF EXISTS notification_type")
