"""Tests for citation metadata verification snapshots."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.citation import CitationSource
from app.services.citation_verification import (
    citation_to_verification_dict,
    verify_citation_metadata,
)
from app.services.review.quality_reviewers import run_book_quality_review


def _citation(**overrides):
    data = {
        "title": "对强人工智能及其理论预设的考察",
        "authors": ["王佳", "朱敏"],
        "year": 2010,
        "journal": "心智与计算",
        "doi": "10.1000/example",
        "url": "",
        "document_type": "journal_article",
        "abstract_preview": "本文讨论强人工智能理论预设。",
        "source": CitationSource.uploaded_file,
        "external_source": "",
        "external_id": "",
        "metadata_status": "complete",
        "volume": "4",
        "issue": "1",
        "pages": "1-7",
        "source_file_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_uploaded_cnki_style_record_with_abstract_is_user_uploaded_only():
    result = citation_to_verification_dict(_citation(doi=""))

    assert result["verification_status"] == "user_uploaded_only"
    assert result["missing_fields"] == []
    assert result["source_match"]["has_abstract"] is True


def test_uploaded_academic_record_without_abstract_needs_verification():
    result = citation_to_verification_dict(_citation(abstract_preview=""))

    assert result["verification_status"] == "needs_verification"
    assert "abstract" in result["missing_fields"]
    assert "uploaded_academic_missing_abstract" in result["reasons"]


def test_doi_lookup_verified_when_metadata_matches():
    def lookup_doi(_doi: str):
        return {
            "title": "对强人工智能及其理论预设的考察",
            "authors": ["王佳", "朱敏"],
            "year": 2010,
            "doi": "10.1000/example",
            "source": "crossref",
        }

    result = verify_citation_metadata(_citation(), lookup_doi=lookup_doi)

    assert result["verification_status"] == "verified"
    assert result["source_match"]["provider"] == "crossref_doi"
    assert result["source_match"]["doi_match"] is True
    assert result["source_match"]["title_similarity"] >= 0.9


def test_doi_lookup_mismatch_when_doi_resolves_to_different_title():
    def lookup_doi(_doi: str):
        return {
            "title": "Completely Different Paper",
            "authors": ["Someone Else"],
            "year": 2022,
            "doi": "10.1000/example",
            "source": "crossref",
        }

    result = verify_citation_metadata(_citation(), lookup_doi=lookup_doi)

    assert result["verification_status"] == "mismatch"
    assert result["source_match"]["provider"] == "crossref_doi"
    assert result["source_match"]["title_similarity"] < 0.5


def test_title_search_probable_without_doi():
    def search_openalex(_query: str, _rows: int):
        return [
            {
                "title": "对强人工智能及其理论预设的考察",
                "authors": ["王佳"],
                "year": 2010,
                "doi": "",
                "url": "https://example.test/work",
            }
        ]

    result = verify_citation_metadata(_citation(doi=""), search_openalex=search_openalex)

    assert result["verification_status"] in {"verified", "probable"}
    assert result["source_match"]["provider"] == "openalex"
    assert result["source_match"]["title_similarity"] >= 0.9


def test_book_quality_review_uses_verification_mismatch_as_manual_high_risk():
    context = {
        "citations": [
            {
                "title": "错误文献",
                "authors": ["张三"],
                "year": 2024,
                "journal": "测试期刊",
                "document_type": "journal_article",
                "metadata_status": "complete",
                "source": "uploaded_file",
                "has_abstract": True,
                "verification_status": "mismatch",
                "recommended_search_query": "错误文献 张三 2024",
            }
        ]
    }

    findings = run_book_quality_review(SimpleNamespace(title="测试书", book_type="academic_monograph"), [], context)

    mismatch = next(item for item in findings if item["issue_type"] == "reference_metadata_mismatch")
    assert mismatch["severity"] == "high"
    assert mismatch["fix_capability"] == "manual_only"
    assert mismatch["verification_status"] == "mismatch"
