"""Project assistant domain migration."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u9v0w1x2y3z4"
down_revision: Union[str, None] = "t8u9v0w1x2y3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("assistant_message", sa.Text(), nullable=False),
        sa.Column("basis_patch", postgresql.JSONB(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_assistant_turns_book_id", "assistant_turns", ["book_id"])

    op.create_table(
        "assistant_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "turn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_turns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("reason_summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
    )
    op.create_index("ix_assistant_traces_turn_id", "assistant_traces", ["turn_id"])


def downgrade() -> None:
    op.drop_index("ix_assistant_traces_turn_id", table_name="assistant_traces")
    op.drop_table("assistant_traces")
    op.drop_index("ix_assistant_turns_book_id", table_name="assistant_turns")
    op.drop_table("assistant_turns")
