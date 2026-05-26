"""figures table

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False：枚举由下方 create() 显式创建，避免 create_table 时重复 CREATE TYPE
figure_type_enum = postgresql.ENUM(
    "flowchart",
    "chart",
    "figure",
    "screenshot",
    name="figure_type",
    create_type=False,
)
figure_status_enum = postgresql.ENUM(
    "pending",
    "generated",
    "uploaded",
    "approved",
    name="figure_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    figure_type_enum.create(bind, checkfirst=True)
    figure_status_enum.create(bind, checkfirst=True)
    op.create_table(
        "figures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("book_id", sa.UUID(), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("figure_number", sa.String(length=20), nullable=True),
        sa.Column("figure_type", figure_type_enum, nullable=False),
        sa.Column("status", figure_status_enum, nullable=False, server_default="pending"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("raw_annotation", sa.Text(), nullable=True),
        sa.Column("render_source", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("position_hint", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_figures_book_id", "figures", ["book_id"], unique=False)
    op.create_index(
        "ix_figures_book_chapter",
        "figures",
        ["book_id", "chapter_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_figures_book_chapter", table_name="figures")
    op.drop_index("ix_figures_book_id", table_name="figures")
    op.drop_table("figures")
    bind = op.get_bind()
    figure_status_enum.drop(bind, checkfirst=True)
    figure_type_enum.drop(bind, checkfirst=True)
