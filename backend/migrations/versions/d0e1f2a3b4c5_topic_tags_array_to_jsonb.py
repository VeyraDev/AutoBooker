"""topic_tags: convert legacy varchar[] to jsonb if needed

Revision ID: d0e1f2a3b4c5
Revises: c4d5e6f7a8b9
Create Date: 2026-05-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'books' "
            "AND column_name = 'topic_tags'"
        )
    ).fetchone()
    if not row:
        return
    udt = row[0]
    if udt in ("_varchar", "_text", "_bpchar"):
        op.execute(
            "ALTER TABLE books ALTER COLUMN topic_tags TYPE jsonb USING to_jsonb(topic_tags)"
        )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'books' "
            "AND column_name = 'topic_tags'"
        )
    ).fetchone()
    if not row or row[0] != "jsonb":
        return
    op.execute(
        "ALTER TABLE books ALTER COLUMN topic_tags TYPE varchar(80)[] USING "
        "CASE WHEN topic_tags IS NULL THEN NULL "
        "ELSE ARRAY(SELECT jsonb_array_elements_text(topic_tags)::varchar(80)) END"
    )
