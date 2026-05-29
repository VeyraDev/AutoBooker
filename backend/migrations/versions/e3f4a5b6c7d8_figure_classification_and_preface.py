"""figure classification columns + books.preface

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN CREATE TYPE figure_source AS ENUM ('writing', 'user_assistant', 'upload'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.add_column("figures", sa.Column("image_type", sa.String(length=64), nullable=True))
    op.add_column("figures", sa.Column("subtype", sa.String(length=64), nullable=True))
    op.add_column("figures", sa.Column("renderer", sa.String(length=32), nullable=True))
    op.add_column(
        "figures",
        sa.Column("classification_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "figures",
        sa.Column("prompt_spec_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "figures",
        sa.Column(
            "figure_source",
            sa.Enum("writing", "user_assistant", "upload", name="figure_source"),
            nullable=True,
            server_default="writing",
        ),
    )
    op.add_column(
        "books",
        sa.Column("preface", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("books", "preface")
    op.drop_column("figures", "figure_source")
    op.drop_column("figures", "prompt_spec_json")
    op.drop_column("figures", "classification_json")
    op.drop_column("figures", "renderer")
    op.drop_column("figures", "subtype")
    op.drop_column("figures", "image_type")
    op.execute("DROP TYPE IF EXISTS figure_source")
