"""Citation verification cache fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "z4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("citations", sa.Column("verification_status", sa.String(32), nullable=True))
    op.add_column("citations", sa.Column("verification_result", postgresql.JSONB(), nullable=True))
    op.add_column("citations", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_citations_verification_status", "citations", ["verification_status"])


def downgrade() -> None:
    op.drop_index("ix_citations_verification_status", table_name="citations")
    op.drop_column("citations", "last_verified_at")
    op.drop_column("citations", "verification_result")
    op.drop_column("citations", "verification_status")
