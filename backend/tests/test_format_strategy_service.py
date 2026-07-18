"""FormatStrategyService unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.book_format_strategy import BookFormatStrategy, FormatStrategyStatus
from app.models.chapter import Chapter
from app.services.writing.format_strategy_service import FormatStrategyService, _normalize_chapter_suggestions


class _StrategyQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._book_id = None
        self._status = None

    def filter(self, *args, **_kwargs):
        for arg in args:
            if hasattr(arg, "left") and hasattr(arg, "right"):
                key = arg.left.key
                val = arg.right.value if hasattr(arg.right, "value") else arg.right
                if key == "book_id":
                    self._book_id = val
                elif key == "status":
                    self._status = val
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        rows = self._matching()
        return rows[0] if rows else None

    def all(self):
        return self._matching()

    def count(self):
        return len(self._rows)

    def _matching(self):
        rows = self._rows
        if self._book_id is not None:
            rows = [r for r in rows if getattr(r, "book_id", None) == self._book_id]
        if self._status is not None:
            rows = [r for r in rows if getattr(r, "status", None) == self._status]
        return rows


class _ChapterQuery:
    def __init__(self, chapters):
        self._chapters = list(chapters)
        self._book_id = None

    def filter(self, *args, **_kwargs):
        for arg in args:
            if hasattr(arg, "left") and hasattr(arg, "right") and arg.left.key == "book_id":
                self._book_id = arg.right.value if hasattr(arg.right, "value") else arg.right
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        if self._book_id is None:
            return self._chapters
        return [c for c in self._chapters if getattr(c, "book_id", None) == self._book_id]


class _IntakeQuery:
    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def first(self):
        return None


class _Db:
    def __init__(self, strategies=None, chapters=None):
        self.strategies = list(strategies or [])
        self.chapters = list(chapters or [])
        self.added: list = []

    def query(self, model):
        if model is BookFormatStrategy:
            return _StrategyQuery(self.strategies + self.added)
        if model is Chapter:
            return _ChapterQuery(self.chapters)
        from app.models.intake import ProjectIntake

        if model is ProjectIntake:
            return _IntakeQuery()
        return _StrategyQuery([])

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = uuid4()
        return None


def test_normalize_chapter_suggestions():
    raw = {
        "1": [{"column_name": "概念梳理", "purpose": "理解核心概念"}],
        "2": [{"column_name": "故障排查", "purpose": "排错"}],
    }
    out = _normalize_chapter_suggestions(raw)
    assert "1" in out and "2" in out
    assert out["2"][0]["column_name"] == "故障排查"


def test_chapter_format_block_differs_by_chapter():
    strategy = BookFormatStrategy(
        id=uuid4(),
        book_id=uuid4(),
        version=1,
        status=FormatStrategyStatus.confirmed,
        chapter_suggestions={
            "1": [{"column_name": "概念梳理", "purpose": "帮助理解", "appearance_condition": "概念章"}],
            "2": [{"column_name": "故障排查", "purpose": "排错", "appearance_condition": "安装章"}],
        },
    )
    svc = FormatStrategyService(_Db())  # type: ignore[arg-type]
    block1 = svc.chapter_format_block(strategy, 1)
    block2 = svc.chapter_format_block(strategy, 2)
    assert "概念梳理" in block1
    assert "故障排查" in block2
    assert "故障排查" not in block1


def test_confirm_syncs_column_labels():
    book_id = uuid4()
    ch1 = SimpleNamespace(
        id=uuid4(),
        book_id=book_id,
        index=1,
        title="引言",
        content={},
    )
    strategy = BookFormatStrategy(
        id=uuid4(),
        book_id=book_id,
        version=1,
        status=FormatStrategyStatus.draft,
        chapter_suggestions={
            "1": [{"column_name": "本章小结", "purpose": "回顾要点"}],
        },
    )
    book = SimpleNamespace(id=book_id)
    db = _Db(strategies=[strategy], chapters=[ch1])
    svc = FormatStrategyService(db)  # type: ignore[arg-type]
    svc.confirm(book, strategy)  # type: ignore[arg-type]
    assert strategy.status == FormatStrategyStatus.confirmed
    assert ch1.content.get("column_labels") == ["本章小结"]


def test_apply_after_outline_generates_and_confirms(monkeypatch):
    book_id = uuid4()
    ch1 = SimpleNamespace(id=uuid4(), book_id=book_id, index=1, title="章1", content={}, summary="")
    book = SimpleNamespace(id=book_id, title="测试", book_type=SimpleNamespace(value="nonfiction"), target_audience="读者", discipline=None)
    strategy = BookFormatStrategy(
        id=uuid4(),
        book_id=book_id,
        version=1,
        status=FormatStrategyStatus.draft,
        chapter_suggestions={"1": [{"column_name": "案例", "purpose": "举例"}]},
    )
    db = _Db(strategies=[strategy], chapters=[ch1])
    svc = FormatStrategyService(db)  # type: ignore[arg-type]

    def _gen(self, book, *, force=False):
        return strategy

    monkeypatch.setattr(FormatStrategyService, "generate", _gen)
    out = svc.apply_after_outline(book, force=True)  # type: ignore[arg-type]
    assert out.status == FormatStrategyStatus.confirmed
    assert ch1.content.get("column_labels") == ["案例"]


def test_generate_applies_llm_payload(monkeypatch):
    book_id = uuid4()
    book = SimpleNamespace(
        id=book_id,
        title="测试书",
        book_type=SimpleNamespace(value="textbook"),
        target_audience="开发者",
        discipline="计算机",
    )
    db = _Db()

    def _fake_generate(self, book, *, force=False):
        strategy = self.get_draft_or_create(book)
        data = {
            "book_level_columns": [{"column_name": "操作步骤", "purpose": "指导操作"}],
            "conditional_columns": [],
            "forbidden_patterns": ["每章相同顺序"],
            "chapter_suggestions": {"1": [{"column_name": "概念梳理", "purpose": "理解"}]},
        }
        from app.services.writing.format_strategy_service import _normalize_columns

        strategy.book_level_columns = _normalize_columns(data["book_level_columns"])
        strategy.forbidden_patterns = data["forbidden_patterns"]
        strategy.chapter_suggestions = _normalize_chapter_suggestions(data["chapter_suggestions"])
        self.db.flush()
        return strategy

    monkeypatch.setattr(FormatStrategyService, "generate", _fake_generate)
    svc = FormatStrategyService(db)  # type: ignore[arg-type]
    result = svc.generate(book)  # type: ignore[arg-type]
    assert result.book_level_columns[0]["column_name"] == "操作步骤"
    assert "1" in result.chapter_suggestions
