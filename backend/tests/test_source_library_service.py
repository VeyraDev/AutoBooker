"""SourceLibraryService unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.book import CreationOrigin
from app.models.intake import IntakeItem, IntakeItemStatus, IntakeItemType
from app.services.sources.source_library_service import SourceLibraryService, _source_status, _source_title


def test_source_title_and_status_helpers():
    item = SimpleNamespace(
        filename="outline.docx",
        text_content=None,
        parsed_preview="Chapter outline here",
        status=SimpleNamespace(value="parsed"),
        item_type=IntakeItemType.upload,
    )
    item.status = __import__("app.models.intake", fromlist=["IntakeItemStatus"]).IntakeItemStatus.parsed
    assert _source_title(item) == "outline.docx"
    assert _source_status(item) == "read"


def test_list_sources_empty_without_intake():
    class _Db:
        def query(self, _model):
            class Q:
                def filter(self, *_a, **_k):
                    return self

                def order_by(self, *_a, **_k):
                    return self

                def first(self):
                    return None

            return Q()

    book = SimpleNamespace(id=uuid4(), creation_origin=CreationOrigin.idea_only)
    svc = SourceLibraryService(_Db())  # type: ignore[arg-type]
    assert svc.list_sources(book) == []


def test_remove_source_marks_item_disabled():
    book_id = uuid4()
    item_id = uuid4()
    item = SimpleNamespace(
        id=item_id,
        intake_id=uuid4(),
        status=IntakeItemStatus.parsed,
    )
    intake = SimpleNamespace(id=item.intake_id, book_id=book_id)

    class _Db:
        def flush(self):
            return None

        def query(self, model):
            class Q:
                def __init__(self, m):
                    self.m = m

                def filter(self, *_a, **_k):
                    return self

                def first(self):
                    if self.m is IntakeItem:
                        return item
                    if self.m.__name__ == "ProjectIntake":
                        return intake
                    return None

            return Q(model)

    book = SimpleNamespace(id=book_id, creation_origin=CreationOrigin.idea_only)
    svc = SourceLibraryService(_Db())  # type: ignore[arg-type]
    svc.remove_source(book, item_id)
    assert item.status == IntakeItemStatus.disabled
