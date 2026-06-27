"""backfill null book scene ai models from legacy ai_model

Revision ID: l9m0n1p2q3r4
Revises: k8l9m0n1o2p3
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "l9m0n1p2q3r4"
down_revision: Union[str, None] = "k8l9m0n1o2p3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE books
        SET outline_ai_model = COALESCE(outline_ai_model, ai_model)
        WHERE outline_ai_model IS NULL AND ai_model IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE books
        SET constitution_ai_model = COALESCE(constitution_ai_model, ai_model)
        WHERE constitution_ai_model IS NULL AND ai_model IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE books
        SET writing_ai_model = COALESCE(writing_ai_model, ai_model)
        WHERE writing_ai_model IS NULL AND ai_model IS NOT NULL
        """
    )


def downgrade() -> None:
    pass
