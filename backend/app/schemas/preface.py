from pydantic import BaseModel, Field


class PrefaceOut(BaseModel):
    enabled: bool = True
    target_words: int = 3000
    brief: str = ""
    summary: str = ""
    text: str = ""
    status: str = "empty"
    word_count: int = 0
    tiptap_json: dict | None = None


class PrefacePut(BaseModel):
    enabled: bool | None = None
    target_words: int | None = Field(default=None, ge=500, le=20000)
    brief: str | None = Field(default=None, max_length=8000)
    summary: str | None = Field(default=None, max_length=2000)
    text: str | None = None
    status: str | None = Field(default=None, max_length=32)
    word_count: int | None = Field(default=None, ge=0)
    tiptap_json: dict | None = None
