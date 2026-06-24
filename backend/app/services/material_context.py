"""章节写作参考资料上下文构建（RAG 扩展点）。"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.agents.document_parser import DocumentParserAgent


class MaterialContextBuilder:
    """预留完整 RAG 替换点；当前委托 DocumentParserAgent.retrieve。"""

    def __init__(self, db: Session, book_id: uuid.UUID) -> None:
        self._db = db
        self._book_id = book_id
        self._parser = DocumentParserAgent(db, book_id)

    def retrieve_for_chapter(self, query: str, *, top_k: int = 4) -> list[str]:
        return self._parser.retrieve(query, top_k=top_k)
