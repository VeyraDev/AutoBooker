"""Regression tests for canonical source ingestion and stage evidence context."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.agents.document_parser import DocumentParserAgent
from app.models.reference import FileLifecycleStatus, FilePurpose, ParseStatus, ReferenceFile
from app.services.assistant.source_retrieve_service import retrieve_source_context
from app.services.sources.source_ingestion_service import SourceIngestionService
from app.services.sources.stage_source_context_service import _chunk_locator, _query_tokens, _score
from app.services.writing.writing_context_builder import WritingContextBuilder


class _InsertDb:
    def __init__(self):
        self.added = []

    def get(self, _model, _row_id):
        return None

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = uuid4()


def test_assistant_upload_reuses_asset_for_canonical_index():
    db = _InsertDb()
    book = SimpleNamespace(id=uuid4())
    item = SimpleNamespace(
        id=uuid4(),
        filename="访谈资料.docx",
        asset_id=uuid4(),
        reference_file_id=None,
    )

    ref = SourceIngestionService(db).ensure_full_text_index(book, item)  # type: ignore[arg-type]

    assert isinstance(ref, ReferenceFile)
    assert ref.asset_id == item.asset_id
    assert ref.parse_status == ParseStatus.pending
    assert ref.lifecycle_status == FileLifecycleStatus.processing
    assert ref.file_purposes == [FilePurpose.reference_material.value]
    assert item.reference_file_id == ref.id


def test_full_text_chunking_keeps_start_middle_end_and_locators(tmp_path):
    text = (
        "START_UNIQUE_FACT\n"
        + "正文资料。" * 250
        + "\nMIDDLE_UNIQUE_FACT\n"
        + "补充资料。" * 250
        + "\nEND_UNIQUE_FACT"
    )
    path = tmp_path / "source.txt"
    path.write_text(text, encoding="utf-8")

    rows = DocumentParserAgent.chunk_with_metadata(str(path), "txt", text)
    combined = "\n".join(str(row["content"]) for row in rows)

    assert "START_UNIQUE_FACT" in combined
    assert "MIDDLE_UNIQUE_FACT" in combined
    assert "END_UNIQUE_FACT" in combined
    assert all(row.get("paragraph_index") for row in rows)


def test_chinese_relevance_and_precise_locator():
    tokens = _query_tokens("傅忠强 中国汽车金融拓荒经历")
    relevant = _score("傅忠强长期参与中国汽车金融业务建设。", tokens)
    unrelated = _score("这是一份烹饪课程说明。", tokens)
    chunk = SimpleNamespace(
        page_number=12,
        heading_path=["第三章", "汽车金融转型"],
        paragraph_index=8,
        chunk_index=3,
    )

    assert relevant > unrelated
    assert _chunk_locator(chunk) == "第12页 · 第三章 > 汽车金融转型 · 第8段"


def test_generation_context_hash_and_prompt_include_source_usage():
    wcb = WritingContextBuilder(SimpleNamespace())  # type: ignore[arg-type]
    item = {
        "source_kind": "upload",
        "source_id": "source-1",
        "chunk_id": "chunk-9",
        "title": "访谈资料.docx",
        "locator": "第12页 · 第8段",
        "content": "傅忠强谈到汽车金融业务的早期实践。",
    }
    base = {
        "must_keep": [],
        "must_avoid": [],
        "material_policy": [],
        "requirements": [],
        "material_terms": [],
        "legacy_user_material": "",
        "source_items": [item],
    }

    block = wcb.to_prompt_block(base)
    changed = {**base, "source_items": [{**item, "chunk_id": "chunk-10"}]}

    assert "来源ID source-1" in block
    assert "第12页 · 第8段" in block
    assert wcb.context_hash(base) != wcb.context_hash(changed)


def test_assistant_retrieval_uses_stage_context(monkeypatch):
    expected = [
        {
            "source_kind": "upload",
            "source_id": "source-1",
            "reference_file_id": "file-1",
            "chunk_id": "chunk-1",
            "title": "资料.pdf",
            "locator": "第3页",
            "content": "正文中的真实片段",
            "score": 0.9,
            "directly_quotable": False,
        }
    ]

    def _retrieve(_self, _book_id, **_kwargs):
        return expected

    monkeypatch.setattr(
        "app.services.sources.stage_source_context_service.StageSourceContextService.retrieve",
        _retrieve,
    )
    book = SimpleNamespace(id=uuid4())
    result = retrieve_source_context(SimpleNamespace(), book, query="真实片段")  # type: ignore[arg-type]

    assert result["count"] == 1
    assert result["segments"][0]["reference_file_id"] == "file-1"
    assert result["segments"][0]["location"] == "第3页"
    assert result["segments"][0]["text"] == "正文中的真实片段"
