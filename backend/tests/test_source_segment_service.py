"""SourceSegmentService unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.source_segment import SegmentType, SourceSegment
from app.services.sources.content_extractors import heuristic_segments
from app.services.sources.source_segment_service import SourceSegmentService


class _SegmentQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._source_id = None
        self._book_id = None
        self._segment_id = None
        self._deleted = False

    def filter(self, *args, **_kwargs):
        for arg in args:
            if hasattr(arg, "left") and hasattr(arg, "right"):
                key = arg.left.key
                val = arg.right.value if hasattr(arg.right, "value") else arg.right
                if key == "source_id":
                    self._source_id = val
                elif key == "book_id":
                    self._book_id = val
                elif key == "id":
                    self._segment_id = val
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def delete(self):
        self._deleted = True
        if self._source_id is not None:
            self._rows = [r for r in self._rows if getattr(r, "source_id", None) != self._source_id]
        return self

    def first(self):
        rows = self._matching()
        return rows[0] if rows else None

    def all(self):
        return self._matching()

    def _matching(self):
        rows = self._rows
        if self._source_id is not None:
            rows = [r for r in rows if getattr(r, "source_id", None) == self._source_id]
        if self._book_id is not None:
            rows = [r for r in rows if getattr(r, "book_id", None) == self._book_id]
        if self._segment_id is not None:
            rows = [r for r in rows if getattr(r, "id", None) == self._segment_id]
        return rows


class _Db:
    def __init__(self, segments=None):
        self.segments = list(segments or [])
        self.added: list[SourceSegment] = []

    def query(self, model):
        if model is SourceSegment:
            return _SegmentQuery(self.segments + self.added)
        return _SegmentQuery([])

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = uuid4()
        return None


def test_heuristic_segments_finds_multiple_types():
    text = """
目录
第一章 引言
第二章 方法
第三章 案例

写作要求：禁止写成趋势报告，必须包含案例与可执行步骤。

参考文献
[1] Smith, J. (2020). AI Marketing.
[2] Lee, A. (2021). Digital Strategy.
""" + "补充背景说明。" * 20
    found = heuristic_segments(text)
    types = {s["segment_type"] for s in found}
    assert len(types) >= 2
    assert "outline" in types or "manuscript" in types
    assert "bibliography" in types or "requirement" in types


def test_sync_policies_to_book_from_confirmed_segments():
    book_id = uuid4()
    source_id = uuid4()
    book = SimpleNamespace(id=book_id, ai_inferred_settings={})
    seg_outline = SourceSegment(
        id=uuid4(),
        book_id=book_id,
        source_id=source_id,
        segment_type=SegmentType.outline,
        summary="目录结构",
        confidence=0.85,
        user_confirmed=True,
    )
    seg_bib = SourceSegment(
        id=uuid4(),
        book_id=book_id,
        source_id=source_id,
        segment_type=SegmentType.bibliography,
        summary="参考文献列表",
        confidence=0.9,
        user_confirmed=True,
    )
    db = _Db([seg_outline, seg_bib])
    SourceSegmentService(db).sync_policies_to_book(book)  # type: ignore[arg-type]
    assert "outline_policy" in book.ai_inferred_settings
    assert "material_policy" in book.ai_inferred_settings


def test_confirm_segment_updates_user_confirmed():
    book_id = uuid4()
    seg_id = uuid4()
    book = SimpleNamespace(id=book_id, ai_inferred_settings={})
    seg = SourceSegment(
        id=seg_id,
        book_id=book_id,
        source_id=uuid4(),
        segment_type=SegmentType.requirement,
        summary="写作要求",
        confidence=0.55,
        user_confirmed=None,
    )
    db = _Db([seg])
    svc = SourceSegmentService(db)  # type: ignore[arg-type]
    updated = svc.confirm_segment(book, seg_id, confirmed=True)
    assert updated.user_confirmed is True


def test_extract_segments_uses_heuristic_when_llm_empty(monkeypatch):
    book_id = uuid4()
    source_id = uuid4()
    book = SimpleNamespace(id=book_id, ai_inferred_settings={})
    item = SimpleNamespace(
        id=source_id,
        parsed_preview="目录\n第一章 引言\n第二章 方法\n\n写作要求：禁止写成趋势报告，必须包含案例。\n\n参考文献\n[1] Smith, J. (2020). AI Marketing.\n"
        + "补充说明：" + "案例素材需覆盖零售与 SaaS 行业。" * 8,
        text_content="",
    )
    db = _Db()

    def _empty_llm(_self, _text):
        return []

    monkeypatch.setattr(SourceSegmentService, "_llm_extract", _empty_llm)
    svc = SourceSegmentService(db)  # type: ignore[arg-type]
    created = svc.extract_segments(book, item)  # type: ignore[arg-type]
    assert len(created) >= 1
    types = {s.segment_type for s in created}
    assert len(types) >= 1
