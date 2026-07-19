"""Add provenance metadata to source-library entries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("intake_items", sa.Column("source_url", sa.String(length=2000), nullable=True))
    op.add_column("intake_items", sa.Column("source_type", sa.String(length=64), nullable=True))
    op.add_column("intake_items", sa.Column("provider", sa.String(length=64), nullable=True))
    op.add_column("intake_items", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("intake_items", sa.Column("source_metadata", postgresql.JSONB(), nullable=True))
    op.create_index("ix_intake_items_source_type", "intake_items", ["source_type"])


def downgrade() -> None:
    op.drop_index("ix_intake_items_source_type", table_name="intake_items")
    op.drop_column("intake_items", "source_metadata")
    op.drop_column("intake_items", "retrieved_at")
    op.drop_column("intake_items", "provider")
    op.drop_column("intake_items", "source_type")
    op.drop_column("intake_items", "source_url")
