"""Allow the review needs_verification severity value."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f0a1b2c3d4e8"
down_revision: Union[str, None] = "f0a1b2c3d4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "book_review_findings",
        "severity",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "chapter_review_issues",
        "severity",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE book_review_findings SET severity = 'medium' WHERE length(severity) > 16"
    )
    op.execute(
        "UPDATE chapter_review_issues SET severity = 'medium' WHERE length(severity) > 16"
    )
    op.alter_column(
        "chapter_review_issues",
        "severity",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.alter_column(
        "book_review_findings",
        "severity",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
