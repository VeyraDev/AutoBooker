from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@localhost:5432/autobooker"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173"

    # 千问 DashScope（OpenAI 兼容；向量嵌入始终走此通道）
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    """万相/图像等原生 API 根路径（非 OpenAI 兼容模式）。"""
    DASHSCOPE_NATIVE_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 25
    CHAT_MODEL: str = "qwen-max"
    CHAT_MODEL_FAST: str = "qwen-turbo"

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"

    # Kimi（Moonshot）
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"

    # 豆包（火山方舟）
    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"

    # 百度千帆
    BAIDU_API_KEY: str = ""
    BAIDU_BASE_URL: str = "https://qianfan.baidubce.com/v2"

    # 智灵网关（OpenAI 兼容统一模型接口）
    ZEELIN_API_KEY: str = ""
    ZEELIN_BASE_URL: str = "https://getways-jumu.zeelin.cn/v1"
    ZEELIN_CHAT_MODEL: str = "DeepSeek-V4-Pro"
    ZEELIN_IMAGE_MODEL: str = "gpt-image-2"
    ZEELIN_IMAGE_SIZE: str = "auto"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Claude（Anthropic 原生 API）
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"

    # Gemini（Google OpenAI 兼容端点）
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Grok（xAI）
    GROK_API_KEY: str = ""
    GROK_BASE_URL: str = "https://api.x.ai/v1"

    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_SECONDS: float = 1.0

    UPLOAD_DIR: str = "./uploads"
    FIGURES_DIR: str = ""
    INTENT_MODEL: str = ""
    """FIGURE 插图管道：zeelin | openai | wanx | auto（有 ZEELIN_API_KEY 时默认 zeelin）。"""
    FIGURE_IMAGE_PROVIDER: str = "auto"
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    OPENAI_IMAGE_SIZE: str = "1024x1024"
    OPENAI_IMAGE_QUALITY: str = "medium"
    OPENAI_IMAGE_TIMEOUT_SEC: float = 180.0
    OPENAI_IMAGE_MAX_RETRIES: int = 2
    """OpenAI 超时/连不上时是否回退万相（需 DASHSCOPE_API_KEY）。"""
    FIGURE_IMAGE_FALLBACK_WANX: bool = True
    """通义万相模型（仅 FIGURE_IMAGE_PROVIDER=wanx 时使用）。"""
    IMAGE_MODEL: str = "wanx-v1"
    """Graphviz bin 目录（可选；未在 PATH 时后端会自动探测 Windows 默认安装路径）。"""
    GRAPHVIZ_BIN_DIR: str = ""

    # AI 检测第三方 API（留空则使用内部规则分）
    AI_DETECT_API_URL: str = ""
    AI_DETECT_API_KEY: str = ""

    # 社群二维码图片 URL
    COMMUNITY_QR_URL: str = ""

    # 可选：提高 GitHub API 限额
    GITHUB_TOKEN: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        return Path(self.UPLOAD_DIR).resolve()

    @property
    def figures_path(self) -> Path:
        if self.FIGURES_DIR.strip():
            return Path(self.FIGURES_DIR).resolve()
        return self.upload_path / "figures"

    @property
    def intent_model(self) -> str:
        if self.INTENT_MODEL.strip():
            return self.INTENT_MODEL.strip()
        from app.llm.providers import default_ai_model

        return default_ai_model()


settings = Settings()
