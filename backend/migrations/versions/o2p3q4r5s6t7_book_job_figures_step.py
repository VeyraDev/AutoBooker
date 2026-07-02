"""book_job_step 增加 figures

Revision ID: o2p3q4r5s6t7
Revises: n1o2p3q4r5s6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o2p3q4r5s6t7"
down_revision: Union[str, None] = "n1o2p3q4r5s6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_value_exists(enum_name: str, value: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = :enum_name AND e.enumlabel = :value
            LIMIT 1
            """
        ),
        {"enum_name": enum_name, "value": value},
    ).scalar()
    return row is not None


def upgrade() -> None:
    if not _enum_value_exists("book_job_step", "figures"):
        op.execute("ALTER TYPE book_job_step ADD VALUE IF NOT EXISTS 'figures' AFTER 'writing'")


def downgrade() -> None:
    pass
