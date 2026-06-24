"""Merge heads and ensure reference_files.ingest_kind exists.

Revision ID: g4h5i6j7k8l9
Revises: c3d4e5f6a7b8, f3a4b5c6d7e8
Create Date: 2026-06-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g4h5i6j7k8l9"
down_revision: Union[str, Sequence[str], None] = ("c3d4e5f6a7b8", "f3a4b5c6d7e8")
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
