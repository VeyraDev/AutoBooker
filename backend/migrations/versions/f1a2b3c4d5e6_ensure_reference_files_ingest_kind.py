"""Ensure reference_files.ingest_kind exists (idempotent for drifted DBs).

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("reference_files")}
    if "ingest_kind" not in cols:
        op.add_column(
            "reference_files",
            sa.Column("ingest_kind", sa.String(length=20), nullable=False, server_default="reference"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("reference_files")}
    if "ingest_kind" in cols:
        op.drop_column("reference_files", "ingest_kind")
