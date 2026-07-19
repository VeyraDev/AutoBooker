import json
from pathlib import Path
from types import SimpleNamespace

from app.schemas.source_search import SourceSearchPlanIn
from app.services.source_search.planner import SourceSearchPlanner


def test_marked_intent_accuracy_is_at_least_90_percent():
    fixture = Path(__file__).parent / "fixtures" / "source_search" / "source_search_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    planner = SourceSearchPlanner()
    correct = sum(
        planner.build(SourceSearchPlanIn(query=case["query"])).intent.kind == case["intent"]
        for case in cases
    )
    assert len(cases) >= 40
    assert correct / len(cases) >= 0.9


def test_explicit_source_selection_overrides_inferred_sources():
    plan = SourceSearchPlanner().build(
        SourceSearchPlanIn(query="城市生活", requested_source_types=["book", "government"])
    )
    assert plan.requested_source_types == ["book", "government"]
    assert set(plan.queries_by_source) == {"book", "government"}


def test_chapter_scope_adds_book_and_chapter_context():
    book = SimpleNamespace(
        title="江南城市史",
        chapters=[SimpleNamespace(index=3, title="河流与商业")],
    )
    plan = SourceSearchPlanner().build(
        SourceSearchPlanIn(query="人口数据", scope="chapter", chapter_index=3),
        book=book,
    )
    assert "江南城市史" in plan.queries_by_source["government"]
    assert "河流与商业" in plan.queries_by_source["government"]


def test_default_fallback_is_general_web_not_person_papers():
    plan = SourceSearchPlanner().build(SourceSearchPlanIn(query="月洞门的空间意义"))
    assert plan.intent.kind == "general_web"
    assert plan.requested_source_types == ["web"]


def test_person_role_query_uses_profile_sources_without_placeholder_title():
    book = SimpleNamespace(title="书稿4", chapters=[])
    plan = SourceSearchPlanner().build(
        SourceSearchPlanIn(query="中国汽车金融拓荒者傅忠强 集鑫 执行总裁"),
        book=book,
    )

    assert plan.intent.kind == "person_profile"
    assert plan.requested_source_types == ["web", "news"]
    assert all("书稿4" not in query for query in plan.queries_by_source.values())


def test_specific_query_is_not_diluted_by_existing_book_title():
    book = SimpleNamespace(title="傅忠强传：中国汽车金融拓荒者", chapters=[])
    plan = SourceSearchPlanner().build(
        SourceSearchPlanIn(query="中国汽车金融拓荒者傅忠强 集鑫执行总裁"),
        book=book,
    )

    assert all(not query.startswith(book.title) for query in plan.queries_by_source.values())
