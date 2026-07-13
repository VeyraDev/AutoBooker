"""Book format strategy tables (Stage 3)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "x2y3z4a5b6c7"
down_revision: Union[str, None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE format_strategy_status AS ENUM ('draft', 'confirmed', 'superseded')"
    )
    op.create_table(
        "book_format_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            postgresql.ENUM(name="format_strategy_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("book_level_columns", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("conditional_columns", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("forbidden_patterns", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("chapter_suggestions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_book_format_strategies_book_id", "book_format_strategies", ["book_id"])

    op.add_column(
        "project_intakes",
        sa.Column("confirmed_format_strategy_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_intakes_confirmed_format_strategy",
        "project_intakes",
        "book_format_strategies",
        ["confirmed_format_strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "generation_context_snapshots",
        sa.Column("format_strategy_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_context_snapshots", "format_strategy_id")
    op.drop_constraint("fk_project_intakes_confirmed_format_strategy", "project_intakes", type_="foreignkey")
    op.drop_column("project_intakes", "confirmed_format_strategy_id")
    op.drop_index("ix_book_format_strategies_book_id", table_name="book_format_strategies")
    op.drop_table("book_format_strategies")
    op.execute("DROP TYPE format_strategy_status")
