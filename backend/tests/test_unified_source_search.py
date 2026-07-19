from app.schemas.source_search import SourceSearchIn, SourceSearchPlanIn
from app.services.source_search.connectors import ConnectorBatch, normalize_item
from app.services.source_search.service import UnifiedSourceSearchService
from app.services.literature.source_registry import SOURCE_REGISTRY, source_capabilities
import time


def _paper(title="A", url="https://example.org/a"):
    return normalize_item(
        {
            "title": title,
            "url": url,
            "authors": ["Author"],
            "year": 2024,
            "journal": "Journal",
            "doi": "10.1/a",
        },
        provider="openalex",
        source_type="paper",
    )


def test_partial_failure_returns_available_results(monkeypatch):
    monkeypatch.setattr(
        "app.services.source_search.service.executable_connectors",
        lambda source_type: ["openalex", "crossref"],
    )

    def execute(connector, **kwargs):
        name = f"{connector}:paper"
        if connector == "crossref":
            return ConnectorBatch(source_type="paper", attempted=[name], failed={name: "timeout"})
        return ConnectorBatch(source_type="paper", attempted=[name], successful=[name], items=[_paper()])

    monkeypatch.setattr("app.services.source_search.service.execute_connector", execute)
    result = UnifiedSourceSearchService().search(
        SourceSearchIn(query="主题论文", requested_source_types=["paper"])
    )
    assert len(result.items) == 1
    assert result.execution.failed_connectors == {"crossref:paper": "timeout"}
    assert any("部分来源检索失败" in warning for warning in result.warnings)


def test_all_successful_empty_connectors_are_reported_as_no_results(monkeypatch):
    monkeypatch.setattr("app.services.source_search.service.executable_connectors", lambda source_type: ["openalex"])
    monkeypatch.setattr(
        "app.services.source_search.service.execute_connector",
        lambda connector, **kwargs: ConnectorBatch(
            source_type="paper",
            attempted=["openalex:paper"],
            successful=["openalex:paper"],
        ),
    )
    result = UnifiedSourceSearchService().search(
        SourceSearchIn(query="主题论文", requested_source_types=["paper"])
    )
    assert result.items == []
    assert result.warnings == ["未找到相关资料。"]


def test_cross_provider_duplicates_are_merged(monkeypatch):
    monkeypatch.setattr(
        "app.services.source_search.service.executable_connectors",
        lambda source_type: ["openalex", "crossref"],
    )

    def execute(connector, **kwargs):
        item = _paper(title="Same", url=f"https://{connector}.example/item")
        item["doi"] = "10.1000/same"
        return ConnectorBatch(
            source_type="paper",
            attempted=[f"{connector}:paper"],
            successful=[f"{connector}:paper"],
            items=[item],
        )

    monkeypatch.setattr("app.services.source_search.service.execute_connector", execute)
    result = UnifiedSourceSearchService().search(
        SourceSearchIn(query="主题论文", requested_source_types=["paper"])
    )
    assert len(result.items) == 1


def test_missing_tavily_is_unavailable_not_zero_results(monkeypatch):
    monkeypatch.setattr("app.services.literature.source_registry.settings.TAVILY_API_KEY", "")
    result = UnifiedSourceSearchService().search(
        SourceSearchIn(query="普通主题资料", requested_source_types=["web"])
    )
    assert result.execution.unavailable_source_types == ["web"]
    assert not any(warning == "未找到相关资料。" for warning in result.warnings)
    assert any("未配置" in warning for warning in result.warnings)


def test_every_visible_source_is_bound_to_real_executors(monkeypatch):
    monkeypatch.setattr("app.services.literature.source_registry.settings.TAVILY_API_KEY", "configured")
    capabilities = source_capabilities()
    for capability in capabilities:
        if not capability["available"]:
            continue
        assert capability["connectors"]
        for connector in capability["connectors"]:
            assert connector in SOURCE_REGISTRY
            assert SOURCE_REGISTRY[connector].get("executor")


def test_connector_timeout_returns_failure_semantics_not_500(monkeypatch):
    monkeypatch.setattr("app.services.source_search.service.executable_connectors", lambda source_type: ["openalex"])
    monkeypatch.setattr("app.services.source_search.service.settings.SOURCE_SEARCH_TIMEOUT_SEC", 0.01)

    def slow_connector(*args, **kwargs):
        time.sleep(1.2)
        return ConnectorBatch(source_type="paper")

    monkeypatch.setattr("app.services.source_search.service.execute_connector", slow_connector)
    result = UnifiedSourceSearchService().search(
        SourceSearchIn(query="主题论文", requested_source_types=["paper"])
    )
    assert result.items == []
    assert result.execution.failed_connectors == {"openalex:paper": "连接器超时"}
    assert any("暂时无法完成检索" in warning for warning in result.warnings)


def test_search_accepts_a_prebuilt_plan_without_requiring_query(monkeypatch):
    service = UnifiedSourceSearchService()
    plan = service.plan(SourceSearchPlanIn(query="围城图书", requested_source_types=["book"]))
    monkeypatch.setattr("app.services.source_search.service.executable_connectors", lambda source_type: [])
    result = service.search(SourceSearchIn(plan=plan))
    assert result.query == "围城图书"
    assert result.plan.requested_source_types == ["book"]
