"""LLM 服务商注册表：OpenAI 兼容 + Claude（Anthropic 原生）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

from app.config import settings

Region = Literal["cn", "intl"]


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    region: Region
    api_key_attr: str
    base_url_attr: str
    default_base_url: str
    models: tuple[str, ...]
    native_api: Literal["openai", "anthropic"] = "openai"
    model_labels: Mapping[str, str] = field(default_factory=dict)


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="deepseek",
        label="DeepSeek",
        region="cn",
        api_key_attr="DEEPSEEK_API_KEY",
        base_url_attr="DEEPSEEK_BASE_URL",
        default_base_url="https://api.deepseek.com/v1",
        models=("deepseek-chat", "deepseek-reasoner"),
    ),
    ProviderSpec(
        id="qwen",
        label="千问",
        region="cn",
        api_key_attr="DASHSCOPE_API_KEY",
        base_url_attr="DASHSCOPE_BASE_URL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=("qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"),
    ),
    ProviderSpec(
        id="kimi",
        label="Kimi",
        region="cn",
        api_key_attr="KIMI_API_KEY",
        base_url_attr="KIMI_BASE_URL",
        default_base_url="https://api.moonshot.cn/v1",
        models=("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"),
    ),
    ProviderSpec(
        id="doubao",
        label="豆包",
        region="cn",
        api_key_attr="DOUBAO_API_KEY",
        base_url_attr="DOUBAO_BASE_URL",
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
        models=("doubao-pro-32k", "doubao-lite-32k"),
    ),
    ProviderSpec(
        id="baidu",
        label="百度",
        region="cn",
        api_key_attr="BAIDU_API_KEY",
        base_url_attr="BAIDU_BASE_URL",
        default_base_url="https://qianfan.baidubce.com/v2",
        models=("ernie-4.0-8k", "ernie-3.5-8k"),
    ),
    ProviderSpec(
        id="zeelin",
        label="智灵网关",
        region="cn",
        api_key_attr="ZEELIN_API_KEY",
        base_url_attr="ZEELIN_BASE_URL",
        default_base_url="https://getways-jumu.zeelin.cn/v1",
        models=(
            "gpt-5.5",
            "gpt-5.4",
            "gpt-4.1",
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "qwen-plus",
            "qwen3-max",
            "qwen3.5-plus",
            "DeepSeek-V4-Pro",
            "kimi-k2.5",
            "glm-5",
            "MiniMax-M2.5",
            "Doubao-seed-2-0-pro",
        ),
        model_labels={
            "gpt-5.5": "GPT-5.5",
            "gpt-5.4": "GPT-5.4",
            "gpt-4.1": "GPT-4.1",
            "claude-sonnet-4-6": "Claude Sonnet 4.6",
            "claude-opus-4-6": "Claude Opus 4.6",
            "gemini-2.5-flash": "Gemini 2.5 Flash",
            "gemini-2.5-pro": "Gemini 2.5 Pro",
            "qwen-plus": "Qwen Plus",
            "qwen3-max": "Qwen3 Max",
            "qwen3.5-plus": "Qwen3.5 Plus",
            "DeepSeek-V4-Pro": "DeepSeek V4 Pro",
            "kimi-k2.5": "Kimi K2.5",
            "glm-5": "GLM-5",
            "MiniMax-M2.5": "MiniMax M2.5",
            "Doubao-seed-2-0-pro": "Doubao Pro 128k",
        },
    ),
    ProviderSpec(
        id="openai",
        label="OpenAI",
        region="intl",
        api_key_attr="OPENAI_API_KEY",
        base_url_attr="OPENAI_BASE_URL",
        default_base_url="https://api.openai.com/v1",
        models=("gpt-5.5", "gpt-5.5-pro", "gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini", "o3-mini"),
    ),
    ProviderSpec(
        id="claude",
        label="Claude",
        region="intl",
        api_key_attr="ANTHROPIC_API_KEY",
        base_url_attr="ANTHROPIC_BASE_URL",
        default_base_url="https://api.anthropic.com",
        models=("claude-sonnet-4-20250514", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"),
        native_api="anthropic",
    ),
    ProviderSpec(
        id="gemini",
        label="Gemini",
        region="intl",
        api_key_attr="GEMINI_API_KEY",
        base_url_attr="GEMINI_BASE_URL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        models=("gemini-2.0-flash", "gemini-2.5-pro-preview-03-25"),
    ),
    ProviderSpec(
        id="grok",
        label="Grok",
        region="intl",
        api_key_attr="GROK_API_KEY",
        base_url_attr="GROK_BASE_URL",
        default_base_url="https://api.x.ai/v1",
        models=("grok-2-latest", "grok-2-1212"),
    ),
)

_PROVIDER_BY_ID = {p.id: p for p in PROVIDER_SPECS}

_ZEELIN_CATALOG_GROUPS: tuple[dict[str, object], ...] = (
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "region": "cn",
        "models": (("DeepSeek-V4-Pro", "DeepSeek V4 Pro"),),
    },
    {
        "id": "qwen",
        "label": "Qwen",
        "region": "cn",
        "models": (
            ("qwen-plus", "Qwen Plus"),
            ("qwen3-max", "Qwen3 Max"),
            ("qwen3.5-plus", "Qwen3.5 Plus"),
        ),
    },
    {
        "id": "doubao",
        "label": "Doubao",
        "region": "cn",
        "models": (("Doubao-seed-2-0-pro", "Doubao Pro 128k"),),
    },
    {
        "id": "kimi",
        "label": "Kimi",
        "region": "cn",
        "models": (("kimi-k2.5", "Kimi K2.5"),),
    },
    {
        "id": "glm",
        "label": "GLM",
        "region": "cn",
        "models": (("glm-5", "GLM-5"),),
    },
    {
        "id": "minimax",
        "label": "MiniMax",
        "region": "cn",
        "models": (("MiniMax-M2.5", "MiniMax M2.5"),),
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "region": "intl",
        "models": (
            ("gpt-5.5", "GPT-5.5"),
            ("gpt-5.4", "GPT-5.4"),
            ("gpt-4.1", "GPT-4.1"),
        ),
    },
    {
        "id": "claude",
        "label": "Claude",
        "region": "intl",
        "models": (
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ("claude-opus-4-6", "Claude Opus 4.6"),
        ),
    },
    {
        "id": "gemini",
        "label": "Gemini",
        "region": "intl",
        "models": (
            ("gemini-2.5-flash", "Gemini 2.5 Flash"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ),
    },
)

# 旧书稿 ai_model 无前缀时的推断规则
_MODEL_PREFIX_TO_PROVIDER: tuple[tuple[str, str], ...] = (
    ("deepseek-", "deepseek"),
    ("qwen-", "qwen"),
    ("moonshot-", "kimi"),
    ("doubao-", "doubao"),
    ("ernie-", "baidu"),
    ("gpt-", "openai"),
    ("o1", "openai"),
    ("o3-", "openai"),
    ("claude-", "claude"),
    ("gemini-", "gemini"),
    ("grok-", "grok"),
)


def get_provider_spec(provider_id: str) -> ProviderSpec | None:
    return _PROVIDER_BY_ID.get(provider_id)


def provider_api_key(provider_id: str) -> str:
    spec = get_provider_spec(provider_id)
    if not spec:
        return ""
    return (getattr(settings, spec.api_key_attr, "") or "").strip()


def provider_base_url(provider_id: str) -> str:
    spec = get_provider_spec(provider_id)
    if not spec:
        return ""
    configured = (getattr(settings, spec.base_url_attr, "") or "").strip()
    return configured or spec.default_base_url


def is_provider_configured(provider_id: str) -> bool:
    return bool(provider_api_key(provider_id))


def configured_providers() -> list[ProviderSpec]:
    return [p for p in PROVIDER_SPECS if is_provider_configured(p.id)]


def parse_ai_model(raw: str | None) -> tuple[str, str]:
    """解析 ai_model 为 (provider_id, model_name)。"""
    text = (raw or "").strip()
    if ":" in text:
        provider_id, model = text.split(":", 1)
        provider_id = provider_id.strip()
        model = model.strip()
        if provider_id and model and get_provider_spec(provider_id):
            return provider_id, model

    if text:
        for prefix, provider_id in _MODEL_PREFIX_TO_PROVIDER:
            if text.startswith(prefix) or text == prefix.rstrip("-"):
                return provider_id, text

    default = default_ai_model()
    return parse_ai_model(default)


def format_ai_model(provider_id: str, model: str) -> str:
    return f"{provider_id}:{model}"


def default_ai_model() -> str:
    """返回首个已配置服务商的默认模型（优先智灵网关，其次 DeepSeek、千问）。"""
    preferred_defaults = {
        "zeelin": settings.ZEELIN_CHAT_MODEL,
        "deepseek": settings.DEEPSEEK_CHAT_MODEL,
        "qwen": settings.CHAT_MODEL,
    }
    for preferred in ("zeelin", "deepseek", "qwen"):
        spec = get_provider_spec(preferred)
        if spec and is_provider_configured(preferred):
            default_model = preferred_defaults[preferred]
            if default_model in spec.models:
                return format_ai_model(preferred, default_model)
            return format_ai_model(preferred, spec.models[0])
    for spec in configured_providers():
        return format_ai_model(spec.id, spec.models[0])
    return format_ai_model("deepseek", settings.DEEPSEEK_CHAT_MODEL)


def normalize_ai_model(raw: str | None) -> str:
    """规范化为 provider:model 字符串。"""
    provider_id, model = parse_ai_model(raw)
    return format_ai_model(provider_id, model)


def resolve_book_ai_model(book) -> str:
    """从书稿读取并规范化 ai_model（通用回退）。"""
    raw = (getattr(book, "ai_model", None) or "").strip()
    if not raw:
        return default_ai_model()
    return normalize_ai_model(raw)


def _resolve_scene_model(book, field_name: str) -> str:
    """按场景字段解析模型，空则回退 ai_model。"""
    raw = (getattr(book, field_name, None) or "").strip()
    if raw:
        return normalize_ai_model(raw)
    return resolve_book_ai_model(book)


def resolve_book_outline_model(book) -> str:
    return _resolve_scene_model(book, "outline_ai_model")


def resolve_book_constitution_model(book) -> str:
    return _resolve_scene_model(book, "constitution_ai_model")


def resolve_book_writing_model(book) -> str:
    return _resolve_scene_model(book, "writing_ai_model")


def _zeelin_models_catalog() -> dict:
    providers_out = []
    for group in _ZEELIN_CATALOG_GROUPS:
        providers_out.append(
            {
                "id": group["id"],
                "label": group["label"],
                "region": group["region"],
                "models": [
                    {
                        "id": model_id,
                        "label": label,
                        "value": format_ai_model("zeelin", model_id),
                    }
                    for model_id, label in group["models"]  # type: ignore[index]
                ],
            }
        )
    return {
        "providers": providers_out,
        "default": default_ai_model(),
    }


def llm_models_catalog() -> dict:
    """供前端下拉使用的已配置模型列表。"""
    if is_provider_configured("zeelin"):
        return _zeelin_models_catalog()

    providers_out = []
    for spec in PROVIDER_SPECS:
        if not is_provider_configured(spec.id):
            continue
        providers_out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "region": spec.region,
                "models": [{"id": m, "label": spec.model_labels.get(m, m)} for m in spec.models],
            }
        )
    return {
        "providers": providers_out,
        "default": default_ai_model(),
    }
