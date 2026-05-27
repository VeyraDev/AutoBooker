"""根据光标上下文与文献摘录，生成一句可嵌入正文的叙述性援引。"""

from __future__ import annotations

import logging
import re

from app.config import settings
from app.llm.client import LLMClient
from app.models.book import Book
from app.models.citation import Citation
from app.services.literature_content import build_quote_paragraph
from app.services.literature_profiles import SOURCE_LABELS

logger = logging.getLogger(__name__)


def _clean_llm_sentence(raw: str) -> str:
    s = (raw or "").strip()
    s = re.sub(r'^["\'「」]+|["\'「」]+$', "", s)
    s = re.sub(
        r"^(?:改为|建议改为|修改为|建议修改为|输出|建议)[:：]\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    return s.strip()


def weave_citation_sentence(
    *,
    book: Book,
    citation: Citation,
    context: str = "",
) -> str:
    src = (citation.external_source or "").lower()
    label = SOURCE_LABELS.get(src, "") or src
    snippet = (
        (citation.quotable_snippet or "")
        or (getattr(citation, "abstract_preview", None) or "")
        or ""
    ).strip()[:900]
    ctx = (context or "").strip()[:2000]

    if not ctx and not snippet:
        return build_quote_paragraph(
            in_text_mark="",
            snippet=citation.title[:120] if citation.title else "",
            source_label=label,
            title=citation.title or "",
            source=src,
        )

    prompt = f"""你是学术写作助手。根据光标处上下文，写**一句**中文，自然融入该文献的观点或事实。

硬性要求：
- 只用叙述性援引（如「维基百科《标题》指出：…」「据某某记载：…」），禁止 APA 括号如 (Author, 2020)
- 不要输出「改为：」等修改说明，只输出这一句话
- 与上下文语气、人称一致

上下文（光标附近）：
{ctx or "（无上下文，按文献信息写一句可独立成立的援引）"}

文献标题：{citation.title or ""}
来源：{label}
摘录/摘要：
{snippet or "（无摘录，勿编造具体数据）"}
"""

    try:
        client = LLMClient()
        out = client.chat_completion(
            [{"role": "user", "content": prompt}],
            model=settings.intent_model,
            max_tokens=320,
            temperature=0.35,
        )
        sentence = _clean_llm_sentence(out)
        if sentence and len(sentence) >= 8:
            return sentence
    except Exception as e:
        logger.warning("weave citation LLM failed: %s", e)

    return build_quote_paragraph(
        in_text_mark="",
        snippet=snippet or (citation.title or "")[:120],
        source_label=label,
        title=citation.title or "",
        source=src,
    )
