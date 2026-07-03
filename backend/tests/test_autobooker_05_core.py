from types import SimpleNamespace
from uuid import uuid4

from app.prompts.memory_extract import MEMORY_EXTRACT_PROMPT
from app.prompts.publication_standards import NARRATIVE_TERM_CONSISTENCY
from app.services.citation_nodes import citation_node, replace_markers_with_nodes
from app.services.material_parse_service import merge_outline_with_primary
from app.services.optimization_service import extract_manuscript_sections
from app.services.tiptap_convert import tiptap_json_to_markdown


def test_primary_outline_is_a_program_level_constraint():
    generated = {
        "chapters": [
            {
                "index": 9,
                "title": "AI 改写的标题",
                "summary": "补充摘要",
                "sections": [{"title": "AI 小节"}],
            },
            {"title": "不应保留的多余章节"},
        ]
    }
    primary = [
        {
            "title": "锁定的第一章",
            "sections": [{"title": "锁定小节"}],
        }
    ]

    merged = merge_outline_with_primary(generated, primary)

    assert len(merged["chapters"]) == 1
    assert merged["chapters"][0]["index"] == 1
    assert merged["chapters"][0]["title"] == "锁定的第一章"
    assert merged["chapters"][0]["sections"] == [{"title": "锁定小节"}]
    assert merged["chapters"][0]["summary"] == "补充摘要"


def test_txt_manuscript_uses_heading_rules_and_keeps_locators(tmp_path):
    source = tmp_path / "manuscript.txt"
    source.write_text(
        "第一章 起点\n第一章正文。\n\n第二章 转折\n第二章正文。",
        encoding="utf-8",
    )

    sections = extract_manuscript_sections(str(source), "txt")

    assert [item["title"] for item in sections] == ["起点", "转折"]
    assert sections[0]["body"] == "第一章正文。"
    assert sections[0]["locator"]["line"] == 1
    assert all(item["confidence"] >= 80 for item in sections)


class _CitationQuery:
    def __init__(self, citation):
        self.citation = citation

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.citation


class _CitationDb:
    def __init__(self, citation):
        self.citation = citation

    def query(self, *_args, **_kwargs):
        return _CitationQuery(self.citation)


def _citation():
    return SimpleNamespace(
        id=uuid4(),
        authors=["Ada Lovelace"],
        year=1843,
        title="Notes",
        doi=None,
        url=None,
        external_source=None,
        external_id=None,
        list_index=1,
    )


def test_citation_node_round_trips_through_markdown_export():
    citation = _citation()
    node = citation_node(citation, "apa", locator="p. 12")
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": [node]}]}

    assert node["attrs"]["citationId"] == str(citation.id)
    assert node["attrs"]["nodeId"]
    assert tiptap_json_to_markdown(doc) == "(Lovelace, 1843, p. 12)"


def test_ai_citation_markers_become_nodes_and_unmatched_marks_are_flagged():
    citation = _citation()
    evidence_id = uuid4()
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"内部标记 [[CITE:{citation.id}|{evidence_id}|parenthetical|p. 2]]；"
                            "错误编号 [9]。"
                        ),
                    }
                ],
            }
        ],
    }
    book = SimpleNamespace(id=uuid4(), citation_style=SimpleNamespace(value="apa"))

    converted, unresolved = replace_markers_with_nodes(
        _CitationDb(citation),
        book,
        doc,
    )
    paragraph = converted["content"][0]["content"]

    assert any(node.get("type") == "citation" for node in paragraph)
    assert "[9]" in unresolved
    assert "（待补充来源）" in tiptap_json_to_markdown(converted)


def test_author_year_before_internal_marker_becomes_one_numbered_node():
    citation = _citation()
    citation.authors = ["张磊"]
    citation.year = 2026
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "类似的技术已经开始进入课堂实践"
                            f"（张磊，2026）[[CITE:{citation.id}|parenthetical]]。"
                        ),
                    }
                ],
            }
        ],
    }
    book = SimpleNamespace(id=uuid4(), citation_style=SimpleNamespace(value="apa"))

    converted, unresolved = replace_markers_with_nodes(_CitationDb(citation), book, doc)
    content = converted["content"][0]["content"]
    citation_nodes = [node for node in content if node.get("type") == "citation"]
    plain_text = "".join(node.get("text", "") for node in content if node.get("type") == "text")

    assert unresolved == []
    assert len(citation_nodes) == 1
    assert citation_nodes[0]["attrs"]["citationId"] == str(citation.id)
    assert citation_nodes[0]["attrs"]["displayText"] == "[1]"
    assert "张磊，2026" not in plain_text


def test_term_prompts_allow_empty_non_specialist_glossaries():
    assert "非专业书类允许术语表为空" in NARRATIVE_TERM_CONSISTENCY
    assert "若无则返回 {}" in MEMORY_EXTRACT_PROMPT
    assert "不自动附英文" in NARRATIVE_TERM_CONSISTENCY
