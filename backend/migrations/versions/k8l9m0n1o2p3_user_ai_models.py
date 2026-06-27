"""user scene ai model preferences

Revision ID: k8l9m0n1o2p3
Revises: j7k8l9m0n1o2
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k8l9m0n1o2p3"
down_revision: Union[str, None] = "j7k8l9m0n1o2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("outline_ai_model", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("constitution_ai_model", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("writing_ai_model", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("assistant_ai_model", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "assistant_ai_model")
    op.drop_column("users", "writing_ai_model")
    op.drop_column("users", "constitution_ai_model")
    op.drop_column("users", "outline_ai_model")
