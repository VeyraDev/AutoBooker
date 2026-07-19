"""Link assistant uploads to full-text indexes and track generation sources."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intake_items",
        sa.Column(
            "reference_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reference_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_intake_items_reference_file_id", "intake_items", ["reference_file_id"])
    op.add_column(
        "generation_context_snapshots",
        sa.Column("source_items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("generation_context_snapshots", "source_items")
    op.drop_index("ix_intake_items_reference_file_id", table_name="intake_items")
    op.drop_column("intake_items", "reference_file_id")
