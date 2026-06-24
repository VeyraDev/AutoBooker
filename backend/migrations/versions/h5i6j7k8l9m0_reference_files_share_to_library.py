"""Add reference_files.share_to_library for library sharing.

Revision ID: h5i6j7k8l9m0
Revises: g4h5i6j7k8l9
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h5i6j7k8l9m0"
down_revision: Union[str, None] = "g4h5i6j7k8l9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("reference_files")}
    if "share_to_library" not in cols:
        op.add_column(
            "reference_files",
            sa.Column("share_to_library", sa.String(length=20), nullable=False, server_default="private"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("reference_files")}
    if "share_to_library" in cols:
        op.drop_column("reference_files", "share_to_library")
