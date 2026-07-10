"""Validate export AST structure."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.services.publication.export_assembler import build_book_export_ast


class ExportStructureReviewer:
    def __init__(self, db: Session):
        self.db = db

    def run(self, book: Book, chapters: list[Chapter]) -> list[dict]:
        findings: list[dict] = []
        if not (book.title or "").strip():
            findings.append({"category": "book_structure", "severity": "high", "title": "缺少书名", "detail": "请补充书名"})
        export_ast = build_book_export_ast(book, chapters, self.db)
        has_preface = any(s.type == "preface" for s in export_ast.sections)
        if not has_preface:
            findings.append(
                {
                    "category": "book_structure",
                    "severity": "low",
                    "title": "缺少前言",
                    "detail": "建议补充前言，或在导出时确认是否需要",
                }
            )
        if not any(s.type == "chapter" for s in export_ast.sections):
            findings.append(
                {
                    "category": "export_structure",
                    "severity": "high",
                    "title": "无可导出章节",
                    "detail": "请确认至少有一章正文内容",
                }
            )
        flat = export_ast.flatten_blocks()
        figure_blocks = [b for b in flat if b.role == "figure"]
        for fb in figure_blocks[:10]:
            attrs = fb.attrs or {}
            if not attrs.get("fileUrl") and not attrs.get("figureId"):
                findings.append(
                    {
                        "category": "export_structure",
                        "severity": "medium",
                        "title": "配图缺少可解析 URL",
                        "detail": fb.text or "未命名图",
                    }
                )
        return findings
