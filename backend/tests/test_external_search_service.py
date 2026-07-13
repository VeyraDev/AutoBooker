"""ExternalSearchService 归一化与 API 失败 fallback。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.assistant.external_search_service import ExternalSearchService


def test_search_person_works_normalizes_and_dedupes():
    svc = ExternalSearchService()
    papers = [
        {"title": "Alpha Paper", "year": 2020, "authors": ["A"], "source": "semantic_scholar", "abstract_preview": "alpha"},
        {"title": "alpha paper", "year": 2021, "authors": ["B"], "source": "crossref"},
    ]
    with patch("app.services.assistant.external_search_service.search_semantic_scholar", return_value=papers[:1]):
        with patch("app.services.assistant.external_search_service.search_crossref", return_value=papers[1:]):
            with patch("app.services.assistant.external_search_service.LiteratureAgent") as agent_cls:
                agent_cls.return_value.search.return_value = []
                with patch("app.services.assistant.external_search_service.search_arxiv", return_value=[]):
                    with patch("app.services.assistant.external_search_service.search_wikipedia", return_value=[]):
                        with patch("app.services.assistant.external_search_service._duckduckgo_lite", return_value=[]):
                            data = svc.search_person_works("Alice", institution="MIT", topic="ML")
    assert data["person"] == "Alice"
    assert len(data["works"]) == 1
    assert data["works"][0]["title"] == "Alpha Paper"
    assert "source_scope" in data
    assert isinstance(data["research_directions"], list)


def test_search_person_works_collects_warnings_on_api_failures():
    svc = ExternalSearchService()
    with patch("app.services.assistant.external_search_service.search_semantic_scholar", side_effect=RuntimeError("down")):
        with patch("app.services.assistant.external_search_service.search_crossref", side_effect=RuntimeError("down")):
            with patch("app.services.assistant.external_search_service.LiteratureAgent") as agent_cls:
                agent_cls.return_value.search.side_effect = RuntimeError("down")
                with patch("app.services.assistant.external_search_service.search_arxiv", side_effect=RuntimeError("down")):
                    with patch("app.services.assistant.external_search_service.search_wikipedia", side_effect=RuntimeError("down")):
                        with patch("app.services.assistant.external_search_service._duckduckgo_lite", side_effect=RuntimeError("down")):
                            data = svc.search_person_works("Bob")
    assert data["works"] == []
    assert any("手动上传" in w or "不可用" in w for w in data["warnings"])


def test_search_person_works_requires_name():
    svc = ExternalSearchService()
    with pytest.raises(ValueError, match="person_name"):
        svc.search_person_works("   ")
