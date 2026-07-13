"""Source segments for mixed-file recognition (Stage 2)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, None] = "v0w1x2y3z4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE source_segment_type AS ENUM ("
        "'outline', 'requirement', 'manuscript', 'preface', 'chapter_draft', "
        "'bibliography', 'style_sample', 'case_material', 'table_material', 'figure_material'"
        ")"
    )
    op.create_table(
        "source_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intake_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "segment_type",
            postgresql.ENUM(name="source_segment_type", create_type=False),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("locator", sa.String(500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("suggested_usage", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_source_segments_book_id", "source_segments", ["book_id"])
    op.create_index("ix_source_segments_source_id", "source_segments", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_source_segments_source_id", table_name="source_segments")
    op.drop_index("ix_source_segments_book_id", table_name="source_segments")
    op.drop_table("source_segments")
    op.execute("DROP TYPE source_segment_type")
