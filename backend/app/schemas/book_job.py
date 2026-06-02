from pydantic import BaseModel, Field


class BookJobOut(BaseModel):
    id: str
    book_id: str
    status: str
    current_step: str | None = None
    progress_pct: int = 0
    error_message: str | None = None

    model_config = {"from_attributes": True}


class AutoGenerateIn(BaseModel):
    title: str = Field(..., max_length=500)
    book_type: str = "nonfiction"
    style_type: str = "popular_science"
    discipline: str | None = None
