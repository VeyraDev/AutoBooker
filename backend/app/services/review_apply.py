"""将审校建议落实为可预览的正文修改（直接替换或调用 LLM）。"""

from __future__ import annotations

import re

from app.llm.client import LLMClient
from app.models.book import Book
from app.services.review_anchor import apply_text_edit, build_text_diff, canonical_markdown, locate_issue_anchor, snapshot_hash

_INSTRUCTION_PREFIX = re.compile(
    r"^(?:改为|建议改为|可以改为|可修改为|替换为|修改为|建议修改为|修改为：|改为：|替换为：|建议：|请)\s*",
    re.IGNORECASE,
)

_BAD_REPLACEMENT_PREFIX = re.compile(
    r"^\s*(?:建议改为|建议修改为|可以改为|可修改为|修改为[:：]|改为[:：]|替换为[:：]|建议[:：]|原因[:：]|说明[:：]|分析[:：])"
)


def _clean_replace_text(raw: str) -> str:
    s = (raw or "").strip()
    s = _INSTRUCTION_PREFIX.sub("", s)
    return s.strip()


def validate_replacement_text(action_type: str, replacement_text: str) -> str:
    act = (action_type or "replace").strip().lower()
    text = (replacement_text or "").strip()
    if act == "delete":
        if text:
            raise ValueError("delete 类型不允许携带 replacement_text")
        return ""
    if act in {"replace", "revise"}:
        if not text:
            raise ValueError("replace/revise 类型需要 replacement_text")
        if _BAD_REPLACEMENT_PREFIX.search(text):
            raise ValueError("replacement_text 必须是最终正文，不能包含“建议/原因/说明”等说明式前缀")
    if act == "insert" and not text:
        raise ValueError("insert 类型需要 replacement_text")
    return text


def preview_issue_application(
    *,
    current_markdown: str,
    issue_snapshot_hash: str,
    quote: str,
    action_type: str,
    replacement_text: str,
    paragraph_id: str | None = None,
    paragraph_index: int | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    min_confidence: float = 0.72,
) -> dict:
    current_md = canonical_markdown(current_markdown)
    current_hash = snapshot_hash(current_md)
    action = (action_type or "replace").strip().lower()
    replacement = validate_replacement_text(action, replacement_text)
    located = locate_issue_anchor(
        current_md,
        quote=quote,
        paragraph_id=paragraph_id,
        paragraph_index=paragraph_index,
        char_start=char_start if current_hash == issue_snapshot_hash else None,
        char_end=char_end if current_hash == issue_snapshot_hash else None,
    )
    if located.char_start is None or located.char_end is None:
        raise ValueError("无法定位该审校建议，请重新审校或手动修改")
    preview_required = current_hash != issue_snapshot_hash or located.confidence < min_confidence
    after = apply_text_edit(
        current_md,
        start=located.char_start,
        end=located.char_end,
        replacement=replacement,
        action=action,
    )
    return {
        "before_hash": current_hash,
        "after_hash": snapshot_hash(after),
        "result_markdown": after,
        "result_text": replacement,
        "preview_kind": "insert" if action == "insert" else "delete" if action == "delete" else "replace",
        "diff": build_text_diff(current_md, after, start=located.char_start, end=located.char_end),
        "locator_strategy": located.strategy,
        "locator_confidence": located.confidence,
        "preview_required": preview_required,
        "stale": current_hash != issue_snapshot_hash,
        "paragraph_id": located.paragraph_id,
        "paragraph_index": located.paragraph_index,
        "char_start": located.char_start,
        "char_end": located.char_end,
        "anchor_hash": located.anchor_hash,
        "quote": located.quote or quote,
    }


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
        validate_replacement_text(act, "")
        return "", "delete"

    if act == "replace":
        text = _clean_replace_text(sug)
        if not text and detail:
            text = _clean_replace_text(detail)
        validate_replacement_text(act, text)
        return text, "replace"

    if act == "insert":
        if sug and not _looks_like_instruction(sug):
            validate_replacement_text(act, sug)
            return sug, "insert"
        text = _llm_edit(book, chat_model, q, sug or detail, ctx, mode="insert")
        validate_replacement_text(act, text)
        return text, "insert"

    # revise — 用 AI 按说明改写 quote
    instr = sug or detail
    if not q:
        raise ValueError("revise 类型需要可定位的原文片段 quote")
    text = _llm_edit(book, chat_model, q, instr, ctx, mode="revise")
    validate_replacement_text("replace", text)
    return text, "replace"


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
