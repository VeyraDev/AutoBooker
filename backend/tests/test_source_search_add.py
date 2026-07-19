from types import SimpleNamespace
from uuid import uuid4

from app.models.intake import IntakeItemStatus, IntakeItemType
from app.routers import sources as sources_router
from app.schemas.source_search import SourceSearchResultAddIn
from app.services.sources.source_library_service import SourceLibraryService


def _item(source_type="web", citeability=True):
    return {
        "id": "item-1",
        "title": "公开页面",
        "url": "https://example.com/page",
        "snippet": "只保存这段检索摘要",
        "authors": ["作者"],
        "publisher": "example.com",
        "published_at": "2026-07-01",
        "year": 2026,
        "source_type": source_type,
        "provider": "tavily",
        "domain": "example.com",
        "relevance": 0.8,
        "credibility_hint": "unknown",
        "citeability": citeability,
        "metadata_missing": [],
        "document_type": source_type,
        "doi": "",
        "isbn": "",
        "external_id": "https://example.com/page",
        "journal": "",
        "degraded": False,
    }


def test_source_library_persists_snippet_and_provenance_only(monkeypatch):
    intake = SimpleNamespace(id=uuid4())
    created = SimpleNamespace(
        id=uuid4(),
        status=IntakeItemStatus.parsed,
        item_type=IntakeItemType.pasted_text,
        source_url=None,
        source_type=None,
        provider=None,
        source_metadata=None,
        retrieved_at=None,
        filename=None,
        parsed_preview=None,
        detected_roles=None,
    )

    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return None

    class Db:
        def query(self, model):
            return Query()

        def flush(self):
            return None

    svc = SourceLibraryService(Db())
    monkeypatch.setattr(svc, "_ensure_intake", lambda book: intake)

    def add_text(item_intake, text, item_type):
        assert item_intake is intake
        assert text == "只保存这段检索摘要"
        assert item_type == IntakeItemType.pasted_text
        created.text_content = text
        return created

    monkeypatch.setattr(svc._intake_items, "add_text_item", add_text)
    row = svc.add_search_result(SimpleNamespace(id=uuid4()), _item())
    assert row.source_url == "https://example.com/page"
    assert row.provider == "tavily"
    assert row.source_metadata["published_at"] == "2026-07-01"
    assert "raw_content" not in row.source_metadata


def test_citation_add_rechecks_metadata_and_ignores_client_claim(monkeypatch):
    book = SimpleNamespace(id=uuid4())
    user = SimpleNamespace(id=uuid4())

    class Db:
        def commit(self):
            return None

    monkeypatch.setattr(sources_router.book_service, "get_book_or_404", lambda *args: book)

    def should_not_create(*args, **kwargs):
        raise AssertionError("web result must not become a citation")

    monkeypatch.setattr(sources_router, "create_citation_from_paper", should_not_create)
    result = sources_router.add_source_search_results(
        book.id,
        SourceSearchResultAddIn(target="citation_library", items=[_item(citeability=True)]),
        user,
        Db(),
    )
    assert result.added_count == 0
    assert result.rejected[0]["reason"] == "文献元数据不完整"
