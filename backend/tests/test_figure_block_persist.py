from unittest.mock import MagicMock
from uuid import UUID, uuid4

from app.models.figure import FigureSource, FigureStatus, FigureType
from app.services.figure_service import ensure_figure_blocks_persisted, resolve_figure_for_block


def test_resolve_figure_for_block_creates_when_stale_id(monkeypatch):
    book_id = uuid4()
    chapter_index = 8
    stale_id = str(uuid4())
    stored: list = []

    monkeypatch.setattr(
        "app.services.figure_service.get_chapter_figures",
        lambda _bid, _ch, _db: list(stored),
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    def _flush():
        for call in db.add.call_args_list:
            fig = call.args[0]
            if getattr(fig, "id", None) is None:
                fig.id = uuid4()
            if fig not in stored:
                stored.append(fig)

    db.flush.side_effect = _flush

    fig, attrs = resolve_figure_for_block(
        book_id,
        chapter_index,
        {
            "figureId": stale_id,
            "rawAnnotation": "家庭 AI 学习闭环",
            "figureType": "figure",
        },
        db=db,
        figures_by_id={},
        existing=stored,
        used=set(),
    )

    assert attrs["figureId"] == str(fig.id)
    assert UUID(str(attrs["figureId"]))
    assert fig.raw_annotation == "家庭 AI 学习闭环"
    assert fig.figure_type == FigureType.figure
    assert fig.status == FigureStatus.pending
    assert fig.figure_source == FigureSource.writing


def test_ensure_figure_blocks_persisted_patches_doc(monkeypatch):
    book_id = uuid4()
    chapter_index = 8
    stored: list = []

    monkeypatch.setattr(
        "app.services.figure_service.get_chapter_figures",
        lambda _bid, _ch, _db: list(stored),
    )
    monkeypatch.setattr(
        "app.services.figure_service.renumber_chapter_figures_from_tiptap",
        lambda *_a, **_k: None,
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    def _flush():
        for call in db.add.call_args_list:
            fig = call.args[0]
            if getattr(fig, "id", None) is None:
                fig.id = uuid4()
            if fig not in stored:
                stored.append(fig)

    db.flush.side_effect = _flush

    doc = {
        "type": "doc",
        "content": [
            {
                "type": "figureBlock",
                "attrs": {
                    "figureId": str(uuid4()),
                    "rawAnnotation": "示意图",
                    "figureType": "figure",
                },
            }
        ],
    }

    ensure_figure_blocks_persisted(book_id, chapter_index, doc, db)
    new_id = doc["content"][0]["attrs"]["figureId"]
    assert new_id
    assert any(str(f.id) == new_id for f in stored)
