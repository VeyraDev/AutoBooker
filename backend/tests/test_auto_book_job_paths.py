from types import SimpleNamespace

from app.services import auto_book_job
from app.services.assistant.suggest_book_settings import apply_book_settings_suggestion
from app.services.writing.project_seed import _heuristic_title_from_seed, resolve_project_seed


class _Dumpable:
    def __init__(self, value):
        self.value = value

    def model_dump(self, **_kwargs):
        return self.value


class _Db:
    def __init__(self):
        self.flushed = False

    def flush(self):
        self.flushed = True


def test_outline_title_replaces_placeholder_even_without_optimization():
    book = SimpleNamespace(title="书稿1", allow_title_optimization=False)

    auto_book_job._maybe_apply_outline_title(book, {"title": "中国汽车金融拓荒之路"})

    assert book.title == "中国汽车金融拓荒之路"


def test_settings_completion_applies_suggested_title():
    book = SimpleNamespace(title="书稿1")

    applied = apply_book_settings_suggestion(
        book,
        {"suggestions": {"title": "中国汽车金融拓荒者"}},
    )

    assert book.title == "中国汽车金融拓荒者"
    assert applied["title"] == "中国汽车金融拓荒者"


def test_numbered_placeholder_is_not_part_of_project_seed():
    book = SimpleNamespace(
        id=None,
        title="书稿4",
        topic_brief="AI赋能家庭教育",
        user_material="",
    )

    assert resolve_project_seed(book) == "AI赋能家庭教育"


def test_title_fallback_uses_first_meaningful_seed_line():
    assert _heuristic_title_from_seed("AI赋能家庭教育\n书稿4") == "AI赋能家庭教育"


def test_resolved_title_is_recorded_in_inferred_settings():
    book = SimpleNamespace(title="AI赋能家庭教育", ai_inferred_settings={"book_type": "nonfiction"})

    auto_book_job._record_resolved_title(book)

    assert book.ai_inferred_settings["title"] == "AI赋能家庭教育"


def test_auto_book_search_uses_unified_dynamic_plan(monkeypatch):
    captured = {}
    response = SimpleNamespace(
        query="人物传记 傅忠强",
        plan=SimpleNamespace(
            intent=_Dumpable({"kind": "person_profile"}),
            requested_source_types=["web", "news"],
        ),
        execution=_Dumpable({"attempted_connectors": ["tavily"]}),
        model_dump=lambda **_kwargs: {"items": []},
    )

    class _Search:
        def search(self, body, *, book):
            captured["body"] = body
            captured["book"] = book
            return response

    monkeypatch.setattr(auto_book_job, "UnifiedSourceSearchService", lambda: _Search())
    db = _Db()
    book = SimpleNamespace(last_literature_query=None)

    result = auto_book_job._search_auto_book_sources(
        db,
        book,
        "人物传记 傅忠强",
    )

    assert result == {"items": []}
    assert captured["body"].scope == "book"
    assert captured["body"].requested_source_types == []
    assert book.last_literature_query["requested_source_types"] == ["web", "news"]
    assert db.flushed is True
