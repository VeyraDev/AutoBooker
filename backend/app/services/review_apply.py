"""将审校建议落实为可预览的正文修改（直接替换或调用 LLM）。"""

from __future__ import annotations

import re

from app.llm.client import LLMClient
from app.models.book import Book

_INSTRUCTION_PREFIX = re.compile(
    r"^(?:改为|建议改为|修改为|建议修改为|修改为：|改为：|建议：|请)\s*",
    re.IGNORECASE,
)


def _clean_replace_text(raw: str) -> str:
    s = (raw or "").strip()
    s = _INSTRUCTION_PREFIX.sub("", s)
    return s.strip()


def apply_review_issue_text(
    *,
    book: Book,
    chat_model: str,
    action_type: str,
    quote: str,
    suggestion: str,
    detail: str = "",
    context: str = "",
) -> tuple[str, str]:
    """
    返回 (result_text, preview_kind)。
    preview_kind: replace | insert | delete
    """
    act = (action_type or "replace").strip().lower()
    q = (quote or "").strip()
    sug = (suggestion or "").strip()
    ctx = (context or "").strip()[:12000]

    if act == "delete":
        return "", "delete"

    if act == "replace":
        text = _clean_replace_text(sug)
        if not text and detail:
            text = _clean_replace_text(detail)
        return text, "replace"

    if act == "insert":
        if sug and not _looks_like_instruction(sug):
            return sug, "insert"
        return _llm_edit(book, chat_model, q, sug or detail, ctx, mode="insert"), "insert"

    # revise — 用 AI 按说明改写 quote
    instr = sug or detail
    if not q:
        raise ValueError("revise 类型需要可定位的原文片段 quote")
    return _llm_edit(book, chat_model, q, instr, ctx, mode="revise"), "replace"


def _looks_like_instruction(s: str) -> bool:
    t = s.strip()
    if len(t) > 100:
        return True
    markers = ("统一", "建议", "改为", "或改为", "应该", "不宜", "避免", "补充", "勿", "不要")
    return any(m in t for m in markers)


def _llm_edit(
    book: Book,
    chat_model: str,
    quote: str,
    instruction: str,
    context: str,
    *,
    mode: str,
) -> str:
    client = LLMClient()
    if mode == "insert":
        system = (
            "你是专业中文编辑。根据审校说明，在【锚点原文】附近写出一小段应插入正文的文字。"
            "只输出要插入的完整句子或短段，不要解释、不要「改为：」前缀。"
        )
        user = (
            f"插入说明：{instruction}\n\n"
            f"锚点原文：\n{quote}\n\n"
            f"章节上下文：\n{context[:8000] if context else '（无）'}"
        )
    else:
        system = (
            "你是专业中文编辑。根据审校说明改写【待改原文】。"
            "只输出改写后的完整正文片段，可直接替换原文，不要解释或「改为：」前缀。"
        )
        user = (
            f"修改说明：{instruction}\n\n"
            f"待改原文：\n{quote}\n\n"
            f"章节上下文：\n{context[:8000] if context else '（无）'}"
        )
    out = client.chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=chat_model,
        max_tokens=2048,
        temperature=0.45,
    )
    return _clean_replace_text(out)
