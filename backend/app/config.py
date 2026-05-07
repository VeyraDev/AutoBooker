from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@localhost:5432/autobooker"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173"

    # DashScope (OpenAI-compatible)
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 25
    CHAT_MODEL: str = "qwen-max"
    CHAT_MODEL_FAST: str = "qwen-turbo"
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_SECONDS: float = 1.0

    # DeepSeek（OpenAI 兼容）：大纲 / 章节正文；需同时保留上方 DashScope 做向量
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"

    UPLOAD_DIR: str = "./uploads"

    def use_deepseek_writer(self) -> bool:
        return bool((self.DEEPSEEK_API_KEY or "").strip())

    def default_writer_model(self) -> str:
        """章节/大纲生成默认模型：配置了 DeepSeek 优先，否则 DashScope。"""
        if self.use_deepseek_writer():
            return self.DEEPSEEK_CHAT_MODEL
        return self.CHAT_MODEL

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        return Path(self.UPLOAD_DIR).resolve()


settings = Settings()
