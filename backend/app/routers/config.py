from fastapi import APIRouter

from app.llm.providers import llm_models_catalog

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/llm-models")
def get_llm_models():
    """返回已配置 API Key 的 LLM 服务商与模型列表（供前端模型切换）。"""
    return llm_models_catalog()
