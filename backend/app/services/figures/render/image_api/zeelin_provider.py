"""FIGURE 管道：智灵网关 OpenAI 兼容图像接口。"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.figures.render.image_api.canvas import canvas_profile_for_subtype
from app.services.figures.render.image_api.pipeline import build_figure_prompt

logger = logging.getLogger(__name__)

_TASK_POLL_INTERVAL_SECONDS = 3.0
_TASK_PENDING_STATUSES = {"pending", "processing", "running", "created", "submitted", "queued"}
_TASK_FAILED_STATUSES = {"failed", "failure", "error", "cancelled", "canceled"}


def _zeelin_base_url() -> str:
    return ((settings.ZEELIN_BASE_URL or "").strip() or "https://getways-jumu.zeelin.cn/v1").rstrip("/")


def _pick_size(model: str, *, sub_kind: str = "figure") -> str:
    raw = (settings.ZEELIN_IMAGE_SIZE or "").strip()
    if raw and raw.lower() not in {"auto", "adaptive"}:
        return raw

    profile = canvas_profile_for_subtype(sub_kind)
    if profile.key == "landscape":
        return "1536x864"
    if profile.key == "portrait":
        return "864x1536"
    return "1024x1024"


def _image_generation_body(model: str, prompt: str, *, sub_kind: str = "figure") -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt[:12000],
        "size": _pick_size(model, sub_kind=sub_kind),
        "n": 1,
    }
    quality = (settings.OPENAI_IMAGE_QUALITY or "").strip()
    if quality and model.lower().startswith("gpt-image"):
        body["quality"] = quality
    return body


def _response_error(resp: httpx.Response) -> RuntimeError:
    try:
        data = resp.json()
    except Exception:
        data = None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return RuntimeError(f"智灵图像生成失败: {err['message']}")
        if data.get("message"):
            return RuntimeError(f"智灵图像生成失败: {data['message']}")
    return RuntimeError(f"智灵图像生成失败 (HTTP {resp.status_code}): {resp.text[:800]}")


def _first_image_item(data: dict[str, Any]) -> dict[str, Any]:
    items = data.get("data")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    output = data.get("output")
    if isinstance(output, dict):
        results = output.get("results")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            return results[0]
        return output
    return data


def _has_image_result(payload: dict[str, Any]) -> bool:
    item = _first_image_item(payload)
    b64 = item.get("b64_json") or item.get("b64") or item.get("base64")
    if isinstance(b64, str) and b64:
        return True
    url = item.get("url") or item.get("image_url") or item.get("image") or payload.get("url")
    return isinstance(url, str) and bool(url)


def _image_task_id(payload: dict[str, Any]) -> str | None:
    if _has_image_result(payload):
        return None
    task_id = payload.get("task_id") or payload.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        return None
    status = str(payload.get("status") or "").strip().lower()
    if not status or status in _TASK_PENDING_STATUSES:
        return task_id.strip()
    return None


def _task_failure_message(payload: dict[str, Any]) -> str | None:
    err = payload.get("error")
    if isinstance(err, dict) and err.get("message"):
        return str(err["message"])
    if isinstance(err, str) and err:
        return err
    status = str(payload.get("status") or "").strip().lower()
    if status in _TASK_FAILED_STATUSES:
        return str(payload.get("message") or payload)
    return None


def _poll_image_task(
    client: httpx.Client,
    *,
    model: str,
    headers: dict[str, str],
    task_id: str,
    deadline_monotonic: float,
) -> dict[str, Any]:
    url = f"{_zeelin_base_url()}/images/result"
    last_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline_monotonic:
        resp = client.post(url, headers=headers, json={"model": model, "task_id": task_id})
        if resp.status_code >= 400:
            raise _response_error(resp)
        payload = resp.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Zeelin image result is not an object: {payload}")
        if _has_image_result(payload):
            return payload
        failure = _task_failure_message(payload)
        if failure:
            raise RuntimeError(f"Zeelin image task failed: {failure}")
        last_payload = payload
        time.sleep(_TASK_POLL_INTERVAL_SECONDS)

    raise RuntimeError(f"Zeelin image task timed out: task_id={task_id}, last={last_payload}")


def _write_image_result(client: httpx.Client, payload: dict[str, Any], output_path: Path) -> None:
    item = _first_image_item(payload)
    b64 = item.get("b64_json") or item.get("b64") or item.get("base64")
    if isinstance(b64, str) and b64:
        output_path.write_bytes(base64.b64decode(b64.split(",", 1)[-1]))
        return

    url = item.get("url") or item.get("image_url") or item.get("image") or payload.get("url")
    if isinstance(url, str) and url.startswith("data:image"):
        output_path.write_bytes(base64.b64decode(url.split(",", 1)[-1]))
        return
    if isinstance(url, str) and url:
        img_resp = client.get(url, timeout=120.0)
        img_resp.raise_for_status()
        output_path.write_bytes(img_resp.content)
        return

    raise RuntimeError(f"智灵图像结果缺少 b64_json 或 url: {payload}")


def generate_figure_image_zeelin(
    description: str,
    output_path: Path,
    *,
    style_type: str = "",
    sub_kind: str = "figure",
    layout_script: str | None = None,
) -> tuple[str, Path]:
    prompt = build_figure_prompt(description, style_type, sub_kind=sub_kind, layout_script=layout_script)
    if not settings.ZEELIN_API_KEY.strip():
        raise RuntimeError("ZEELIN_API_KEY 未配置，无法调用智灵网关图像生成")

    model = (settings.ZEELIN_IMAGE_MODEL or "gpt-image-2").strip()
    url = f"{_zeelin_base_url()}/images/generations"
    headers = {
        "Authorization": f"Bearer {settings.ZEELIN_API_KEY.strip()}",
        "Content-Type": "application/json",
    }
    body = _image_generation_body(model, prompt, sub_kind=sub_kind)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    retries = max(1, settings.OPENAI_IMAGE_MAX_RETRIES)
    timeout = httpx.Timeout(
        connect=60.0,
        read=max(30.0, float(settings.OPENAI_IMAGE_TIMEOUT_SEC)),
        write=60.0,
        pool=30.0,
    )
    last_err: Exception | None = None
    with httpx.Client(timeout=timeout) as client:
        for attempt in range(retries):
            try:
                logger.info(
                    "zeelin images.generate attempt=%s model=%s size=%s",
                    attempt + 1,
                    model,
                    body.get("size"),
                )
                resp = client.post(url, headers=headers, json=body)
                if resp.status_code >= 400:
                    raise _response_error(resp)
                payload = resp.json()
                if not isinstance(payload, dict):
                    raise RuntimeError(f"Zeelin image result is not an object: {payload}")
                task_id = _image_task_id(payload)
                if task_id:
                    logger.info("zeelin images.generate task pending task_id=%s", task_id)
                    payload = _poll_image_task(
                        client,
                        model=model,
                        headers=headers,
                        task_id=task_id,
                        deadline_monotonic=time.monotonic() + max(30.0, float(settings.OPENAI_IMAGE_TIMEOUT_SEC)),
                    )
                _write_image_result(client, payload, output_path)
                return prompt, output_path
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.HTTPStatusError) as e:
                last_err = e
                logger.warning("zeelin images.generate attempt %s failed: %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(settings.LLM_RETRY_BASE_SECONDS * (2**attempt))
            except Exception:
                raise

    raise RuntimeError(f"智灵图像生成超时或无法连接。原始错误: {last_err}") from last_err
