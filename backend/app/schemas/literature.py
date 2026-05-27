from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.citation import CitationOut


class LiteratureSearchIn(BaseModel):
    query: str = Field(default="", max_length=500)
    rows: int = Field(default=20, ge=1, le=50)
    refined_queries: list[str] | None = None
    must_include: list[str] | None = None
    must_exclude: list[str] | None = None
    skip_refine: bool = False


class LiteratureRefineQueryIn(BaseModel):
    scope: Literal["book", "chapter"] = "book"
    chapter_index: int | None = None
    raw_query: str = Field(default="", max_length=500)


class LiteratureRefineQueryOut(BaseModel):
    refined_queries: list[str] = []
    must_include: list[str] = []
    must_exclude: list[str] = []


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
    papers: list[LiteraturePaperOut] = []
    github: list[LiteraturePaperOut] = []
    wiki: list[LiteraturePaperOut] = []
    official_docs: list[LiteraturePaperOut] = []
    refined_queries: list[str] = []
    warnings: list[str] = []
    profile: str = ""
    source_hint: str = ""
    # 兼容旧前端
    items: list[LiteraturePaperOut] = []


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
