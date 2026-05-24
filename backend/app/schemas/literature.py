from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.citation import CitationOut


class LiteratureSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    rows: int = Field(default=20, ge=1, le=50)


class LiteraturePaperOut(BaseModel):
    title: str
    year: int | None = None
    authors: list[str] = []
    journal: str = ""
    doi: str = ""
    citations: int = 0
    type: str | None = None
    source: str | None = None
    source_label: str | None = None
    url: str = ""
    semantic_scholar_id: str | None = None
    external_id: str | None = None
    abstract_preview: str | None = None


class LiteratureSearchOut(BaseModel):
    items: list[LiteraturePaperOut]
    profile: str = ""
    source_hint: str = ""


class LiteratureQuoteBlockOut(BaseModel):
    citation_id: str
    in_text_mark: str
    quote_body: str
    bibliography_line: str
    fetch_status: str = "ok"
    source_label: str = ""
    title: str = ""


class LiteratureInsertQuotesOut(BaseModel):
    quotes: list[LiteratureQuoteBlockOut]
    citations: list[CitationOut] = []


class LiteratureFormatIn(BaseModel):
    paper: dict
    style: str = "apa"
    index: int | None = None

    @field_validator("style")
    @classmethod
    def style_ok(cls, v: str) -> str:
        allowed = {"apa", "mla", "chicago", "gb_t7714"}
        if v not in allowed:
            raise ValueError("style must be one of apa, mla, chicago, gb_t7714")
        return v


class LiteratureFormatOut(BaseModel):
    citation: str
