from pydantic import BaseModel, Field


class BookJobDetailOut(BaseModel):
    book_title: str = ""
    outline_ready: bool = False
    narrative_ready: bool = False
    writing_started: bool = False
    ready_for_editor: bool = False
    total_chapters: int = 0
    chapters_done: int = 0
    current_chapter_index: int | None = None
    figures_total: int = 0
    figures_done: int = 0
    figures_pending: int = 0
    stage_message: str = ""
    started_at: str | None = None
    elapsed_seconds: int = 0
    updated_at: str | None = None


class BookJobOut(BaseModel):
    id: str
    book_id: str
    status: str
    current_step: str | None = None
    progress_pct: int = 0
    error_message: str | None = None
    detail: BookJobDetailOut | None = None

    model_config = {"from_attributes": True}


class AutoGenerateIn(BaseModel):
    title: str = Field(..., max_length=500)
    book_type: str = "nonfiction"
    style_type: str = "popular_science"
    discipline: str | None = None
