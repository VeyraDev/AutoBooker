"""clear writing_ai_model when it only mirrors ai_model (use user default prefs)

Revision ID: j7k8l9m0n1o2
Revises: i6j7k8l9m0n1
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "j7k8l9m0n1o2"
down_revision: Union[str, None] = "i6j7k8l9m0n1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE books
        SET writing_ai_model = NULL
        WHERE writing_ai_model IS NOT NULL
          AND ai_model IS NOT NULL
          AND writing_ai_model = ai_model
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE books
        SET writing_ai_model = ai_model
        WHERE writing_ai_model IS NULL
          AND ai_model IS NOT NULL
        """
    )
