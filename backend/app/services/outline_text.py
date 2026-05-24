"""将已确认章节目录序列化为供 NarrativeAgent / 写作使用的纯文本大纲。"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.chapter import Chapter


def serialize_book_outline_markdown(book_id: uuid.UUID, db: Session) -> str:
    rows = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.index.asc())
        .all()
    )
    chunks: list[str] = []
    for ch in rows:
        meta = ch.content if isinstance(ch.content, dict) else {}
        lines = [f"### 第{ch.index}章　{ch.title}", "", (ch.summary or "").strip()]
        sections = meta.get("sections") or []
        if sections:
            lines.append("")
            lines.append("**小节结构**")
            for sec in sections:
                if isinstance(sec, dict):
                    lines.append(
                        f"- {sec.get('title', '')} — {sec.get('summary', '')}".strip(" —")
                    )
        kps = meta.get("key_points") or []
        if kps:
            lines.append("")
            lines.append("**核心要点**：" + "；".join(str(x) for x in kps))
        ew = meta.get("estimated_words")
        if ew:
            lines.append("")
            lines.append(f"**预估字数**：{ew}")
        chunks.append("\n".join(x for x in lines if x is not None))
    return "\n\n---\n\n".join(chunks) if chunks else "（尚无章节大纲）"
