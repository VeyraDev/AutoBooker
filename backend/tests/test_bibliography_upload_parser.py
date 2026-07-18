from __future__ import annotations

from app.services.bibliography_upload_parser import extract_bibliography_records, parse_bibliography_record
from app.services.citation_service import _citation_metadata_status, _merge_uploaded_paper_metadata


def test_parse_cnki_style_record_with_abstract():
    raw = """[50]王佳,朱敏.对强人工智能及其理论预设的考察——基于中文屋论证的批判视角[J].心智与计算,2010,4(1):1-7.
摘要:强人工智能作为人工智能研究领域中的官方形象,在认知科学的发展进程中起到核心作用。"""

    record = parse_bibliography_record(raw)

    assert record.authors == ["王佳", "朱敏"]
    assert record.title == "对强人工智能及其理论预设的考察——基于中文屋论证的批判视角"
    assert record.document_type == "journal_article"
    assert record.journal == "心智与计算"
    assert record.year == 2010
    assert record.volume == "4"
    assert record.issue == "1"
    assert record.pages == "1-7"
    assert record.abstract_preview and record.abstract_preview.startswith("强人工智能")


def test_extract_records_without_reference_heading():
    text = """[1]张三.人工智能教育应用研究[J].现代教育技术,2024,34(2):10-18.
摘要:本文讨论人工智能教育应用。

[2]李四.智能体协作综述[J].计算机研究,2023,12(1):1-9.
摘要:本文综述智能体协作。"""

    records = extract_bibliography_records(text)

    assert [r.title for r in records] == ["人工智能教育应用研究", "智能体协作综述"]
    assert all(r.abstract_preview for r in records)


def test_uploaded_academic_metadata_requires_abstract():
    complete = {
        "title": "人工智能教育应用研究",
        "authors": ["张三"],
        "year": 2024,
        "doi": "",
        "url": "",
        "source": "user_upload",
        "document_type": "journal_article",
        "abstract_preview": "本文讨论人工智能教育应用。",
    }
    missing_abstract = {**complete, "abstract_preview": ""}

    assert _citation_metadata_status(complete, None) == "complete"
    assert _citation_metadata_status(missing_abstract, None) == "needs_completion"


def test_doi_lookup_metadata_keeps_uploaded_abstract_when_lookup_lacks_it():
    uploaded = {
        "title": "本地题名",
        "authors": ["张三"],
        "year": 2024,
        "doi": "10.1000/example",
        "source": "user_upload",
        "abstract_preview": "本地摘要。",
        "pages": "1-7",
    }
    looked_up = {
        "title": "Remote Title",
        "authors": ["Zhang San"],
        "year": 2024,
        "doi": "10.1000/example",
        "source": "crossref",
    }

    merged = _merge_uploaded_paper_metadata(uploaded, looked_up)

    assert merged["title"] == "Remote Title"
    assert merged["abstract_preview"] == "本地摘要。"
    assert merged["pages"] == "1-7"
