"""写作阶段流水线占位。

当前产品路径为：PUT /books/{id}/outline（confirm_start_writing）+ POST /books/{id}/chapters/{i}/generate（SSE）。
章节生成前会在后端按需生成并缓存 `books.narrative_constitution`（NarrativeAgent），再流式调用 ChapterWriter。
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.book import Book, BookStatus

GenerationMode = Literal["auto", "manual"]


def run_start_writing_pipeline(
    book: Book,
    db: Session,
    generation_mode: GenerationMode,
) -> dict[str, Any]:
    """将书稿标记为写作中；具体章节生成请走章节 SSE 接口。"""
    del generation_mode
    book.status = BookStatus.writing
    db.commit()
    db.refresh(book)
    return {
        "phase": "writing",
        "generation_mode": "manual",
        "narrative_ready": False,
        "chapters_total": 0,
        "chapters_completed": 0,
        "current_chapter_index": None,
        "message": "已进入写作阶段：首次生成章节前将自动准备全书写作规则。",
    }
