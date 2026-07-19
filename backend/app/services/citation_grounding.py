"""章节写作：本书文献与上传资料合并为写作依据。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.book import Book
from app.services.citation_service import in_text_mark, list_citations_sorted

_GROUNDING_CHAR_BUDGET = 7500


def _citation_to_block(citation, style: str) -> str:
    marker = f"[[CITE:{citation.id}|parenthetical]]"
    authors = "; ".join((citation.authors or [])[:3])
    parts = [
        f"{marker} {citation.title}",
        f"作者: {authors or '未知'}",
        f"年份: {citation.year or 'n.d.'}",
    ]
    if citation.external_source:
        parts.append(f"来源: {citation.external_source}")
    if citation.journal:
        parts.append(f"出处: {citation.journal}")
    if citation.doi:
        parts.append(f"DOI: {citation.doi}")
    if citation.url:
        parts.append(f"URL: {citation.url}")
    snippet = (citation.quotable_snippet or "").strip()
    if snippet:
        parts.append(f"可引用片段: {snippet[:600]}")
    abstract = (getattr(citation, "abstract_preview", None) or "").strip()
    if abstract:
        parts.append(f"摘要: {abstract[:500]}")
    return " | ".join(parts)


def build_allowed_citations_block(
    db: Session,
    book: Book,
    *,
    chapter_context: str = "",
    citation_ids: list[str] | None = None,
    max_items: int = 12,
) -> list[str]:
    """全书已批准引用，格式化为写作清单。"""
    style = book.citation_style.value if book.citation_style else "apa"
    rows = list_citations_sorted(db, book.id)
    selected_ids = {str(value) for value in (citation_ids or []) if str(value).strip()}
    if selected_ids:
        rows = [row for row in rows if str(row.id) in selected_ids]
    if not rows:
        return []

    ctx_lower = (chapter_context or "").casefold()
    blocks: list[tuple[int, str]] = []
    for c in rows:
        block = _citation_to_block(c, style)
        score = 0
        title = (c.title or "").casefold()
        if ctx_lower and title and title in ctx_lower:
            score += 2
        for tag in (c.title or "").split()[:4]:
            if len(tag) > 2 and tag.casefold() in ctx_lower:
                score += 1
        blocks.append((score, block))

    blocks.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in blocks[:max_items]]


def merge_grounding_for_writer(
    db: Session,
    book: Book,
    rag_snippets: list[str],
    *,
    chapter_context: str = "",
    char_budget: int = _GROUNDING_CHAR_BUDGET,
    citation_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    返回 (citation_blocks, rag_snippets_trimmed)。
    citation_blocks 单独注入 user 消息；rag 在预算内截断。
    """
    citation_blocks = build_allowed_citations_block(
        db, book, chapter_context=chapter_context, citation_ids=citation_ids
    )
    cite_chars = sum(len(b) for b in citation_blocks)
    remaining = max(500, char_budget - cite_chars)

    rag_out: list[str] = []
    used = 0
    for s in rag_snippets:
        piece = s if len(s) <= 400 else s[:400] + "…"
        if used + len(piece) > remaining:
            break
        rag_out.append(piece)
        used += len(piece)

    return citation_blocks, rag_out


def build_citation_policy_block(has_citations: bool, has_rag: bool) -> str:
    lines = [
        "=== 引用与事实来源（强制）===",
        "正文中的引用、数据与具体案例只能来自下方【已批准本书文献】与【上传资料检索片段】。",
        "禁止引用未在清单中出现的论文、书籍或研究（包括训练语料中的经典论文）。",
        "若需提及某观点但清单中无对应来源，使用「（待补充来源）」或改为不具名的原理性表述。",
        "禁止写「研究表明」「有数据显示」「据报道」而不给出清单内对应标注。",
        "引用时必须原样使用清单中以 [[CITE:...]] 开头的内部标记；系统会把它转换为规范引用。",
        "不要自己生成 APA 括号、GB/T 编号或最终参考文献编号，也不要改写标记中的 UUID。",
    ]
    if not has_citations and not has_rag:
        lines.append(
            "当前无已批准引用与上传资料：禁止编造具体数字、公司案例、实验与人名时间地点齐全的故事；"
            "可使用原理说明，或明确标注「以下为假设性说明」。"
        )
    return "\n".join(lines)
