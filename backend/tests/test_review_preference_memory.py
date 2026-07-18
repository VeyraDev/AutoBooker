from types import SimpleNamespace
from uuid import uuid4

from app.models.chapter import Chapter
from app.models.chapter_review import ChapterReviewIssue
from app.models.project_memory import ProjectMemory, ProjectMemoryStrength, ProjectMemoryType
from app.services.review.review_preference_memory import record_review_preference
from app.services.review.review_workspace_service import ReviewWorkspaceService
from app.services.writing.writing_context_builder import WritingContextBuilder


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _MemoryDb:
    def __init__(self):
        self.rows: list[ProjectMemory] = []

    def query(self, model):
        if model is ProjectMemory:
            return _Query(self.rows)
        return _Query([])

    def add(self, row):
        self.rows.append(row)

    def flush(self):
        return None


def test_record_review_preference_upserts_coarse_dismissed_memory():
    db = _MemoryDb()
    book_id = uuid4()

    record_review_preference(
        db,  # type: ignore[arg-type]
        book_id,
        decision="dismissed",
        product_dimension="ai_text_risk",
        issue_type="generic_summary",
        fix_capability="observe_only",
    )
    record_review_preference(
        db,  # type: ignore[arg-type]
        book_id,
        decision="dismissed",
        product_dimension="ai_text_risk",
        issue_type="generic_summary",
        fix_capability="observe_only",
    )

    assert len(db.rows) == 1
    row = db.rows[0]
    assert row.memory_type == ProjectMemoryType.decision
    assert row.strength == ProjectMemoryStrength.preference
    assert row.confirmed is True
    assert "用户曾忽略或拒绝" in row.content
    assert "AI 文本风险 / generic_summary" in row.content


def test_recorded_review_preference_enters_prompt_block():
    db = _MemoryDb()
    book_id = uuid4()
    record_review_preference(
        db,  # type: ignore[arg-type]
        book_id,
        decision="accepted",
        product_dimension="publication_delivery",
        issue_type="figure_table_numbering",
        fix_capability="preview_apply",
    )

    block = WritingContextBuilder(db).to_prompt_block(  # type: ignore[arg-type]
        {
            "book_id": str(book_id),
            "must_keep": [],
            "must_avoid": [],
            "material_policy": [],
            "outline_policy": [],
            "requirements": [],
            "material_terms": [],
            "legacy_user_material": "",
        }
    )

    assert "项目长期记忆" in block
    assert "用户曾接受" in block
    assert "出版交付 / figure_table_numbering" in block


class _WorkspaceDb:
    def __init__(self, issue, chapter):
        self.issue = issue
        self.chapter = chapter
        self.flushed = False

    def get(self, model, row_id):
        if model is ChapterReviewIssue and row_id == self.issue.id:
            return self.issue
        if model is Chapter and row_id == self.chapter.id:
            return self.chapter
        return None

    def flush(self):
        self.flushed = True


def _issue(chapter_id):
    return SimpleNamespace(
        id=uuid4(),
        chapter_id=chapter_id,
        title="空泛总结",
        explanation="段落只有总结，没有新增信息。",
        quote="总之，这一问题非常重要。",
        replacement_text=None,
        issue_type="generic_summary",
        detector="quality",
        dimension="style_consistency",
        severity="low",
        quality_evidence={
            "product_dimension": "ai_text_risk",
            "fix_capability": "preview_apply",
        },
        char_start=0,
        paragraph_id=None,
        paragraph_index=0,
        applied_at=None,
        resolved_at=None,
        status="open",
    )


def test_patch_finding_records_review_preference(monkeypatch):
    book_id = uuid4()
    chapter = SimpleNamespace(id=uuid4(), book_id=book_id, index=1, title="第一章")
    issue = _issue(chapter.id)
    db = _WorkspaceDb(issue, chapter)
    svc = ReviewWorkspaceService(db)  # type: ignore[arg-type]
    svc._context_snapshot = lambda _book_id: {}  # type: ignore[method-assign]
    svc._chapter_map = lambda _book_id: {chapter.id: chapter}  # type: ignore[method-assign]
    calls: list[dict] = []

    def _record(_db, _book_id, **kwargs):
        calls.append({"book_id": _book_id, **kwargs})

    monkeypatch.setattr(
        "app.services.review.review_workspace_service.record_review_preference",
        _record,
    )

    dto = svc.patch_finding(book_id, issue.id, "chapter", "dismissed")

    assert dto is not None
    assert issue.status == "dismissed"
    assert db.flushed is True
    assert calls == [
        {
            "book_id": book_id,
            "decision": "dismissed",
            "product_dimension": "ai_text_risk",
            "issue_type": "generic_summary",
            "fix_capability": "preview_apply",
        }
    ]
