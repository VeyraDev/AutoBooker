from app.services.source_search import connectors


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self, *, post_payload=None, get_payload=None, **kwargs):
        self.post_payload = post_payload
        self.get_payload = get_payload
        self.last_json = None
        self.last_params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json):
        self.last_json = json
        assert json["include_raw_content"] is False
        return _Response(self.post_payload)

    def get(self, url, params):
        self.last_params = params
        return _Response(self.get_payload)


def test_tavily_transform_does_not_request_full_page(monkeypatch):
    monkeypatch.setattr(connectors.settings, "TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        connectors.httpx,
        "Client",
        lambda **kwargs: _Client(
            post_payload={
                "results": [
                    {
                        "title": "城市更新政策发布",
                        "url": "https://example.gov.cn/policy/1",
                        "content": "政策摘要",
                        "score": 0.91,
                        "published_date": "2026-07-01",
                    }
                ]
            }
        ),
    )
    rows = connectors.search_tavily("城市更新", source_type="government", rows=5)
    assert rows[0]["source_type"] == "government"
    assert rows[0]["provider"] == "tavily"
    assert rows[0]["snippet"] == "政策摘要"


def test_open_library_transform_has_stable_book_metadata(monkeypatch):
    client = _Client(
        get_payload={
            "docs": [
                {
                    "key": "/works/OL1W",
                    "title": "围城",
                    "author_name": ["钱锺书"],
                    "first_publish_year": 1947,
                    "publisher": ["生活书店"],
                    "isbn": ["9780000000001"],
                }
            ]
        }
    )
    monkeypatch.setattr(
        connectors.httpx,
        "Client",
        lambda **kwargs: client,
    )
    rows = connectors.search_open_library("围城图书", rows=5)
    assert client.last_params["title"] == "围城"
    assert rows[0]["url"] == "https://openlibrary.org/works/OL1W"
    assert rows[0]["citeability"] is True
    assert rows[0]["metadata_missing"] == []


def test_tavily_failure_uses_explicit_degraded_fallback(monkeypatch):
    monkeypatch.setattr(connectors.settings, "SOURCE_SEARCH_ALLOW_DDG_FALLBACK", True)
    monkeypatch.setattr(connectors, "search_tavily", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(connectors, "_duckduckgo_lite", lambda query, limit: [("标题", "https://example.com/a", "摘要")])
    batch = connectors.execute_connector("tavily", source_type="web", query="主题", rows=5)
    assert batch.degraded is True
    assert batch.items[0]["degraded"] is True
    assert "tavily:web" in batch.failed
    assert "duckduckgo_lite:web" in batch.successful


def test_web_result_cannot_enter_citation_library_by_metadata_alone():
    item = {
        "title": "网页",
        "authors": ["作者"],
        "year": 2026,
        "publisher": "example.com",
        "url": "https://example.com",
    }
    citeable, missing = connectors.citation_metadata("web", item)
    assert missing == []
    assert citeable is False


def test_academic_failure_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(
        connectors,
        "search_academic",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    batch = connectors.execute_connector("openalex", source_type="paper", query="topic", rows=5)
    assert batch.successful == []
    assert batch.failed == {"openalex:paper": "provider down"}


def test_shared_http_client_identifies_the_application():
    with connectors._http_client() as client:
        assert "https://github.com/VeyraDev/AutoBooker" in client.headers["User-Agent"]
