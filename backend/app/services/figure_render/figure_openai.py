"""FIGURE 管道：OpenAI Images API（gpt-image-1 / dall-e-3 等）。"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import httpx
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from app.config import settings
from app.services.figure_render.figure_ai import build_figure_prompt

logger = logging.getLogger(__name__)

_DALLE3_SIZES = frozenset({"1024x1024", "1792x1024", "1024x1792"})


def _openai_client() -> OpenAI:
    key = settings.OPENAI_API_KEY.strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法调用 OpenAI 图像生成")
    base = (settings.OPENAI_BASE_URL or "").strip() or None
    sec = max(30.0, float(settings.OPENAI_IMAGE_TIMEOUT_SEC))
    timeout = httpx.Timeout(connect=60.0, read=sec, write=60.0, pool=30.0)
    return OpenAI(api_key=key, base_url=base, timeout=timeout, max_retries=0)


def _pick_size(model: str) -> str:
    raw = (settings.OPENAI_IMAGE_SIZE or "1024x1024").strip()
    m = model.lower()
    if m.startswith("dall-e-3") and raw not in _DALLE3_SIZES:
        return "1024x1024"
    return raw


def _build_kwargs(model: str, prompt: str) -> dict:
    size = _pick_size(model)
    kwargs: dict = {
        "model": model,
        "prompt": prompt[:4000],
        "size": size,
        "n": 1,
    }
    mlow = model.lower()
    if mlow.startswith("dall-e-3"):
        kwargs["quality"] = (settings.OPENAI_IMAGE_QUALITY or "standard").strip()
        kwargs["response_format"] = "b64_json"
    elif mlow.startswith("dall-e-2"):
        kwargs["response_format"] = "b64_json"
    else:
        q = (settings.OPENAI_IMAGE_QUALITY or "medium").strip()
        if q:
            kwargs["quality"] = q
    return kwargs


def _write_response_item(item, output_path: Path) -> None:
    if getattr(item, "b64_json", None):
        output_path.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        with httpx.Client(timeout=120.0) as http:
            r = http.get(item.url)
            r.raise_for_status()
            output_path.write_bytes(r.content)
    else:
        raise RuntimeError("OpenAI 图像结果缺少 b64_json 与 url")


def generate_figure_image_openai(
    description: str,
    output_path: Path,
    *,
    style_type: str = "",
    sub_kind: str = "figure",
) -> tuple[str, Path]:
    prompt = build_figure_prompt(description, style_type, sub_kind=sub_kind)
    model = (settings.OPENAI_IMAGE_MODEL or "gpt-image-1").strip()
    client = _openai_client()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = _build_kwargs(model, prompt)

    retries = max(1, settings.OPENAI_IMAGE_MAX_RETRIES)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            logger.info(
                "openai images.generate attempt=%s model=%s size=%s",
                attempt + 1,
                model,
                kwargs.get("size"),
            )
            resp = client.images.generate(**kwargs)
            if not resp.data:
                raise RuntimeError("OpenAI 未返回图像数据")
            _write_response_item(resp.data[0], output_path)
            return prompt, output_path
        except (APITimeoutError, APIConnectionError, RateLimitError, httpx.TimeoutException) as e:
            last_err = e
            logger.warning("openai images.generate attempt %s failed: %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(settings.LLM_RETRY_BASE_SECONDS * (2**attempt))
        except Exception as e:
            last_err = e
            logger.warning("openai images.generate attempt %s failed: %s", attempt + 1, e)
            if attempt < retries - 1 and isinstance(
                e, (APITimeoutError, APIConnectionError, httpx.HTTPError)
            ):
                time.sleep(settings.LLM_RETRY_BASE_SECONDS * (2**attempt))
            else:
                raise

    raise RuntimeError(
        "OpenAI 图像生成超时或无法连接（国内网络需代理或设置 FIGURE_IMAGE_PROVIDER=wanx）。"
        f" 原始错误: {last_err}"
    ) from last_err
