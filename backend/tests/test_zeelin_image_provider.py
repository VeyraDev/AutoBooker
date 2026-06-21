from __future__ import annotations

import base64
from pathlib import Path

from app.config import settings
from app.services.figures.render.image_api import pipeline
from app.services.figures.render.image_api import zeelin_provider


def test_image_provider_auto_prefers_zeelin(monkeypatch):
    monkeypatch.setattr(settings, "FIGURE_IMAGE_PROVIDER", "auto")
    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "dashscope-key")

    assert pipeline.resolve_figure_image_provider() == "zeelin"


def test_zeelin_image_provider_posts_openai_compatible_body(monkeypatch, tmp_path: Path):
    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = ""
        content = b""

        def json(self):
            return {"data": [{"b64_json": base64.b64encode(b"png-bytes").decode("ascii")}]}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

        def get(self, *args, **kwargs):
            raise AssertionError("b64 response should not download image URL")

    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ZEELIN_BASE_URL", "https://gateway.test/v1/")
    monkeypatch.setattr(settings, "ZEELIN_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setattr(settings, "ZEELIN_IMAGE_SIZE", "auto")
    monkeypatch.setattr(settings, "OPENAI_IMAGE_QUALITY", "medium")
    monkeypatch.setattr(settings, "OPENAI_IMAGE_MAX_RETRIES", 1)
    monkeypatch.setattr(zeelin_provider.httpx, "Client", FakeClient)

    prompt, path = zeelin_provider.generate_figure_image_zeelin(
        "用户注册流程",
        tmp_path / "figure.png",
        sub_kind="process_flow",
    )

    assert path.read_bytes() == b"png-bytes"
    assert "用户注册流程" in prompt
    assert captured["url"] == "https://gateway.test/v1/images/generations"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "gpt-image-2"
    assert captured["json"]["size"] == "1536x864"
    assert captured["json"]["quality"] == "medium"


def test_zeelin_image_provider_polls_pending_task(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, dict]] = []

    class FakeResponse:
        status_code = 200
        text = ""
        content = b""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, headers, json):
            calls.append((url, json))
            if url.endswith("/images/generations"):
                return FakeResponse({"status": "pending", "task_id": "task-1", "message": "created"})
            if url.endswith("/images/result"):
                return FakeResponse({"data": [{"b64_json": base64.b64encode(b"png-bytes").decode("ascii")}]})
            raise AssertionError(f"unexpected URL: {url}")

        def get(self, *args, **kwargs):
            raise AssertionError("b64 response should not download image URL")

    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ZEELIN_BASE_URL", "https://gateway.test/v1")
    monkeypatch.setattr(settings, "ZEELIN_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setattr(settings, "ZEELIN_IMAGE_SIZE", "auto")
    monkeypatch.setattr(settings, "OPENAI_IMAGE_MAX_RETRIES", 1)
    monkeypatch.setattr(settings, "OPENAI_IMAGE_TIMEOUT_SEC", 30)
    monkeypatch.setattr(zeelin_provider, "_TASK_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(zeelin_provider.httpx, "Client", FakeClient)

    _prompt, path = zeelin_provider.generate_figure_image_zeelin("task poll", tmp_path / "figure.png")

    assert path.read_bytes() == b"png-bytes"
    assert calls[0][0] == "https://gateway.test/v1/images/generations"
    assert calls[1][0] == "https://gateway.test/v1/images/result"
    assert calls[1][1] == {"model": "gpt-image-2", "task_id": "task-1"}


def test_zeelin_image_provider_respects_explicit_configured_size(monkeypatch, tmp_path: Path):
    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = ""
        content = b""

        def json(self):
            return {"data": [{"b64_json": base64.b64encode(b"png-bytes").decode("ascii")}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, _url, *, headers, json):
            captured["json"] = json
            return FakeResponse()

        def get(self, *args, **kwargs):
            raise AssertionError("b64 response should not download image URL")

    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ZEELIN_BASE_URL", "https://gateway.test/v1")
    monkeypatch.setattr(settings, "ZEELIN_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setattr(settings, "ZEELIN_IMAGE_SIZE", "1024x1024")
    monkeypatch.setattr(settings, "OPENAI_IMAGE_MAX_RETRIES", 1)
    monkeypatch.setattr(zeelin_provider.httpx, "Client", FakeClient)

    zeelin_provider.generate_figure_image_zeelin("用户注册流程", tmp_path / "figure.png", sub_kind="process_flow")

    assert captured["json"]["size"] == "1024x1024"
