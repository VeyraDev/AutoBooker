"""review issue quality evidence

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
# chapter_review_issues is created on sibling branch (b1c2d3e4f5a6); must run after it.
depends_on: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "chapter_review_issues" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("chapter_review_issues")}
    if "quality_evidence" in cols:
        return
    op.add_column(
        "chapter_review_issues",
        sa.Column("quality_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "chapter_review_issues" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("chapter_review_issues")}
    if "quality_evidence" not in cols:
        return
    op.drop_column("chapter_review_issues", "quality_evidence")
