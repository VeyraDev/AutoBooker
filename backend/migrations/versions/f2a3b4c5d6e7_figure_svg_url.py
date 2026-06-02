"""figures.svg_url

Revision ID: f2a3b4c5d6e7
Revises: e3f4a5b6c7d8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("figures", sa.Column("svg_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("figures", "svg_url")
