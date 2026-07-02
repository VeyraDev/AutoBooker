from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services.figures.render.image_api import pipeline


def test_should_fallback_to_wanx_on_billing_limit():
    err = RuntimeError(
        "Error code: 400 - {'error': {'message': 'Billing hard limit has been reached.', "
        "'code': 'billing_hard_limit_reached'}}"
    )
    assert pipeline._should_fallback_to_wanx(err) is True


def test_should_not_fallback_on_unknown_error():
    assert pipeline._should_fallback_to_wanx(ValueError("invalid prompt")) is False


def test_generate_figure_image_falls_back_to_wanx_on_billing_error(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "FIGURE_IMAGE_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setattr(settings, "FIGURE_IMAGE_FALLBACK_WANX", True)

    def _fail_openai(*args, **kwargs):
        raise RuntimeError("Billing hard limit has been reached.")

    def _wanx_ok(description, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"wanx-png")
        return "prompt", output_path

    monkeypatch.setattr(
        "app.services.figures.render.image_api.openai_provider.generate_figure_image_openai",
        _fail_openai,
    )
    monkeypatch.setattr(
        "app.services.figures.render.image_api.wanx_provider.generate_figure_image_wanx",
        _wanx_ok,
    )

    out = tmp_path / "figure.png"
    _prompt, path = pipeline.generate_figure_image("测试图", out)
    assert path.read_bytes() == b"wanx-png"
