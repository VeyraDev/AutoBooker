"""Remove headings emitted by the retired book-column feature."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f0a1b2c3d4e6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RETIRED_HEADINGS = (
    "家长手记",
    "研究速览",
    "风险提示",
    "工具雷达",
    "亲子共试",
    "效能自检",
    "概念梳理",
    "提示词模板",
    "对比示例",
    "操作步骤",
    "踩坑提示",
    "项目流程",
    "案例全程",
    "案例示范",
    "全景回顾",
    "规划模板",
    "风险清单",
    "应对策略",
    "家庭约定模板",
)


def upgrade() -> None:
    alternatives = "|".join(_RETIRED_HEADINGS)
    pattern = (
        rf"(^|\n)[ \t]*(?:\*\*)?(?:{alternatives})(?:\*\*)?"
        rf"[ \t]*(?:\r?\n|$)"
    )
    statement = sa.text(
        """
        WITH cleaned AS (
            SELECT
                id,
                regexp_replace(content ->> 'text', :pattern, :replacement, 'g') AS body
            FROM chapters
            WHERE content IS NOT NULL
              AND content ? 'text'
              AND (content ->> 'text') ~ :pattern
        )
        UPDATE chapters AS chapter
        SET content = jsonb_set(
            chapter.content - 'tiptap_json',
            '{text}',
            to_jsonb(cleaned.body),
            true
        )
        FROM cleaned
        WHERE chapter.id = cleaned.id
        """
    )
    op.get_bind().execute(statement, {"pattern": pattern, "replacement": r"\1"})


def downgrade() -> None:
    # Generated headings cannot be reconstructed without reintroducing retired data.
    pass
