"""Move the generated bibliography out of ordinary chapters.

Revision ID: q4r5s6t7u8v9
Revises: p3q4r5s6t7u8
Create Date: 2026-07-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "q4r5s6t7u8v9"
down_revision: Union[str, None] = "p3q4r5s6t7u8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("bibliography", postgresql.JSONB(), nullable=True))
    op.execute(
        """
        UPDATE books AS b
        SET bibliography = (
            SELECT jsonb_build_object(
                'title', '参考文献',
                'text', COALESCE(c.content ->> 'text', ''),
                'tiptap_json', COALESCE(c.content -> 'tiptap_json', '{"type":"doc","content":[]}'::jsonb)
            )
            FROM chapters AS c
            WHERE c.book_id = b.id
              AND lower(trim(c.title)) IN ('参考文献', 'references', '参考书目', '引用文献')
            ORDER BY c.index DESC
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM chapters AS c
            WHERE c.book_id = b.id
              AND lower(trim(c.title)) IN ('参考文献', 'references', '参考书目', '引用文献')
        )
        """
    )
    op.execute(
        """
        DELETE FROM chapters
        WHERE lower(trim(title)) IN ('参考文献', 'references', '参考书目', '引用文献')
        """
    )


def downgrade() -> None:
    op.drop_column("books", "bibliography")
