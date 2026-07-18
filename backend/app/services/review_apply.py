"""将审校建议落实为可预览的正文修改（直接替换或调用 LLM）。"""

from __future__ import annotations

import re

from app.llm.client import LLMClient
from app.models.book import Book
from app.services.review_anchor import apply_text_edit, build_text_diff, canonical_markdown, locate_issue_anchor, snapshot_hash

FULL_CHAPTER_APPLY_TYPES = {
    "full_chapter_replace",
    "figure_table_normalize",
    "first_line_indent",
}

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


def preview_full_chapter_application(
    *,
    current_markdown: str,
    issue_snapshot_hash: str,
    result_markdown: str,
    apply_type: str = "full_chapter_replace",
    result_tiptap_json: dict | None = None,
) -> dict:
    """Create a review application preview for deterministic whole-chapter fixes."""
    current_md = canonical_markdown(current_markdown)
    after = canonical_markdown(result_markdown)
    action = (apply_type or "full_chapter_replace").strip().lower()
    if action not in FULL_CHAPTER_APPLY_TYPES:
        raise ValueError("不支持的整章预览类型")
    if not after:
        raise ValueError("整章预览结果为空")
    if after == current_md:
        raise ValueError("未检测到可应用的格式修改")
    current_hash = snapshot_hash(current_md)
    diff = build_text_diff(current_md, after)
    diff.update(
        {
            "full_chapter": True,
            "full_after": after,
        }
    )
    if isinstance(result_tiptap_json, dict):
        diff["full_after_tiptap"] = result_tiptap_json
    return {
        "before_hash": current_hash,
        "after_hash": snapshot_hash(after),
        "result_markdown": after,
        "result_text": diff.get("after") or "",
        "preview_kind": "replace",
        "diff": diff,
        "locator_strategy": action,
        "locator_confidence": 1.0,
        "preview_required": True,
        "stale": current_hash != issue_snapshot_hash,
        "paragraph_id": None,
        "paragraph_index": None,
        "char_start": diff.get("char_start"),
        "char_end": diff.get("char_end"),
        "anchor_hash": None,
        "quote": diff.get("before") or "",
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
    forbid_vague_ratio_rewrite: bool = False,
) -> tuple[str, str]:
    """
    返回 (result_text, preview_kind)。
    preview_kind: replace | insert | delete
    """
    act = (action_type or "replace").strip().lower()
    q = (quote or "").strip()
    sug = (suggestion or "").strip()
    ctx = (context or "").strip()[:12000]

    if act == "choose":
        raise ValueError("请先选择处理方式后再应用")

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
        text = _llm_edit(
            book,
            chat_model,
            q,
            sug or detail,
            ctx,
            mode="insert",
            forbid_vague_ratio_rewrite=forbid_vague_ratio_rewrite,
        )
        validate_replacement_text(act, text)
        return text, "insert"

    # revise — 用 AI 按说明改写 quote
    instr = sug or detail
    if not q:
        raise ValueError("revise 类型需要可定位的原文片段 quote")
    if forbid_vague_ratio_rewrite and not sug:
        raise ValueError("数据类问题缺少处理说明，拒绝空泛自动改写")
    text = _llm_edit(
        book,
        chat_model,
        q,
        instr,
        ctx,
        mode="revise",
        forbid_vague_ratio_rewrite=forbid_vague_ratio_rewrite,
    )
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
    forbid_vague_ratio_rewrite: bool = False,
) -> str:
    client = LLMClient()
    ban = ""
    if forbid_vague_ratio_rewrite:
        ban = (
            "\n严禁把具体数字改成「相当比例」「同样不低」「不少」「很大一部分」等空泛套话；"
            "要么保留数字并加来源限定，要么用仍含信息的定性描述替换。"
        )
    if mode == "insert":
        system = (
            "你是专业中文编辑。根据审校说明，在【锚点原文】附近写出一小段应插入正文的文字。"
            "只输出要插入的完整句子或短段，不要解释、不要「改为：」前缀。"
            + ban
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
            + ban
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
