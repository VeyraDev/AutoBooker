"""FIGURE 管道：阿里云通义万相（原生异步 API）。"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from app.config import settings
from app.services.figures.render.image_api.canvas import wanx_size_for_canvas
from app.services.figures.render.image_api.pipeline import build_figure_prompt

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 180.0

_WANX_ERROR_HINTS: dict[str, str] = {
    "Arrearage": "通义万相账户欠费或余额不足，请前往阿里云百炼控制台充值后重试",
    "InvalidApiKey": "DASHSCOPE_API_KEY 无效，请检查 .env 配置",
    "AccessDenied": "无权限调用通义万相，请确认 API Key 与模型权限",
}


def _native_api_base() -> str:
    raw = (settings.DASHSCOPE_NATIVE_API_BASE or "").strip()
    if raw:
        return raw.rstrip("/")
    return "https://dashscope.aliyuncs.com/api/v1"


def _auth_headers(*, async_mode: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    if async_mode:
        headers["X-DashScope-Async"] = "enable"
    return headers


def _raise_wanx_error(resp: httpx.Response, *, stage: str) -> None:
    try:
        data = resp.json()
    except Exception:
        data = None
    if isinstance(data, dict):
        code = str(data.get("code") or "")
        message = str(data.get("message") or "").strip()
        hint = _WANX_ERROR_HINTS.get(code)
        if hint:
            raise RuntimeError(f"{hint}（{code}）")
        if message:
            raise RuntimeError(f"万相{stage}失败: {message}")
    raise RuntimeError(f"万相{stage}失败 (HTTP {resp.status_code}): {resp.text[:800]}")


def _uses_v2_endpoint(model: str) -> bool:
    m = model.lower()
    return m.startswith("wan2") or m.startswith("wanx2") or "t2i" in m and m != "wanx-v1"


def _create_wanx_task(client: httpx.Client, prompt: str, model: str, *, size: str) -> str:
    base = _native_api_base()
    if _uses_v2_endpoint(model):
        url = f"{base}/services/aigc/image-generation/generation"
        body = {
            "model": model,
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {
                "size": size,
                "n": 1,
                "prompt_extend": False,
                "watermark": False,
            },
        }
    else:
        url = f"{base}/services/aigc/text2image/image-synthesis"
        body = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {"style": "<auto>", "size": size, "n": 1},
        }

    resp = client.post(url, headers=_auth_headers(async_mode=True), json=body)
    if resp.status_code >= 400:
        _raise_wanx_error(resp, stage="创建任务")
    data = resp.json()
    if data.get("code"):
        code = str(data.get("code"))
        hint = _WANX_ERROR_HINTS.get(code)
        if hint:
            raise RuntimeError(f"{hint}（{code}）")
        raise RuntimeError(f"万相 API 错误: {data.get('message') or data}")
    task_id = (data.get("output") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"万相未返回 task_id: {data}")
    return str(task_id)


def _poll_wanx_task(client: httpx.Client, task_id: str) -> str:
    url = f"{_native_api_base()}/tasks/{task_id}"
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    while time.monotonic() < deadline:
        resp = client.get(url, headers=_auth_headers())
        if resp.status_code >= 400:
            _raise_wanx_error(resp, stage="查询任务")
        data = resp.json()
        output = data.get("output") or {}
        status = output.get("task_status")
        if status == "SUCCEEDED":
            results = output.get("results") or []
            if not results:
                raise RuntimeError("万相任务成功但未返回图片")
            img_url = results[0].get("url")
            if not img_url:
                raise RuntimeError(f"万相结果缺少图片 URL: {results[0]}")
            return str(img_url)
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            msg = output.get("message") or data.get("message") or status
            raise RuntimeError(f"万相任务失败: {msg}")
        time.sleep(POLL_INTERVAL_SEC)
    raise RuntimeError("万相任务超时，请稍后重试")


def generate_figure_image_wanx(
    description: str,
    output_path: Path,
    *,
    style_type: str = "",
    sub_kind: str = "figure",
    layout_script: str | None = None,
) -> tuple[str, Path]:
    prompt = build_figure_prompt(description, style_type, sub_kind=sub_kind, layout_script=layout_script)
    if not settings.DASHSCOPE_API_KEY.strip():
        raise RuntimeError("DASHSCOPE_API_KEY 未配置，无法调用通义万相")

    model = (settings.IMAGE_MODEL or "wanx-v1").strip()
    size = wanx_size_for_canvas(subtype=sub_kind)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=60.0) as client:
        task_id = _create_wanx_task(client, prompt, model, size=size)
        logger.info("wanx task created model=%s size=%s task_id=%s", model, size, task_id)
        img_url = _poll_wanx_task(client, task_id)
        img_resp = client.get(img_url)
        img_resp.raise_for_status()
        output_path.write_bytes(img_resp.content)

    return prompt, output_path
