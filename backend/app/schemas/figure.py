from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FigureOut(BaseModel):
    id: UUID
    book_id: UUID
    chapter_index: int
    figure_number: str | None
    figure_type: str
    status: str
    caption: str | None
    raw_annotation: str | None
    file_url: str | None
    svg_url: str | None = None
    quality_report: dict | None = None
    position_hint: str | None
    sort_order: int | None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class FigureListItem(BaseModel):
    id: str
    figure_number: str | None
    type: str
    status: str
    caption: str | None
    chapter: int
    position_hint: str | None
    file_url: str | None = None
    svg_url: str | None = None
    quality_report: dict | None = None
    raw_annotation: str | None = None


class FigureListOut(BaseModel):
    items: list[FigureListItem]


class FigureGenerateIn(BaseModel):
    chart_type: str | None = Field(default=None, max_length=32)
    sub_kind: str | None = Field(default=None, max_length=32)


class FigureCaptionIn(BaseModel):
    caption: str = Field(..., max_length=5000)


class FigureSyncOut(BaseModel):
    tiptap_json: dict


class FigureRefreshIn(BaseModel):
    """可选：传入编辑器当前 TipTap JSON，避免未保存时与库内正文不一致。"""

    tiptap_json: dict | None = None


class FigureRefreshOut(BaseModel):
    items: list[FigureOut]


class FigureTableOverviewItem(BaseModel):
    kind: str
    seq: int
    number: str
    label: str
    title: str
    has_reference: bool
    has_caption: bool
    figure_id: str | None = None
    status: str | None = None


class FigureTableNormalizeIn(BaseModel):
    tiptap_json: dict | None = None


class FigureTableNormalizeOut(BaseModel):
    tiptap_json: dict
    text: str
    overview: list[FigureTableOverviewItem]


class FigureTableCaptionPatchIn(BaseModel):
    tiptap_json: dict
    overview: list[FigureTableOverviewItem]
