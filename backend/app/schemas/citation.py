from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CitationSourceOut(str, Enum):
    literature_search = "literature_search"
    uploaded_file = "uploaded_file"
    manual = "manual"


class CitationPaperIn(BaseModel):
    title: str = ""
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str = ""
    doi: str = ""
    citations: int = 0
    type: str | None = None
    source: str | None = None
    source_label: str | None = None
    url: str | None = None
    semantic_scholar_id: str | None = None
    external_id: str | None = None
    abstract_preview: str | None = None
    document_type: str | None = None
    publisher: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    quotable_snippet: str | None = None


class CitationCreateIn(BaseModel):
    paper: CitationPaperIn
    source: CitationSourceOut = CitationSourceOut.literature_search
    raw_text: str | None = None


class CitationBatchIn(BaseModel):
    papers: list[CitationPaperIn] = Field(min_length=1, max_length=50)
    source: CitationSourceOut = CitationSourceOut.literature_search


class CitationOut(BaseModel):
    id: UUID
    book_id: UUID
    doi: str | None
    title: str
    authors: list[str]
    year: int | None
    journal: str | None
    document_type: str | None = None
    publisher: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    metadata_status: str = "complete"
    format_cache: dict[str, str] | None
    source: CitationSourceOut
    source_file_id: UUID | None
    raw_text: str | None
    external_source: str | None = None
    external_id: str | None = None
    quotable_snippet: str | None = None
    abstract_preview: str | None = None
    url: str | None = None
    list_index: int | None
    formatted: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CitationInsertIn(BaseModel):
    """为所选本书文献生成可插入正文的引用数据。"""

    citation_ids: list[UUID] = Field(min_length=1, max_length=30)


class CitationInsertOut(BaseModel):
    in_text_marks: list[str]
    bibliography_lines: list[str]
    citations: list[CitationOut]


class CitationListOut(BaseModel):
    items: list[CitationOut]


class CitationWeaveIn(BaseModel):
    """根据光标上下文生成一句叙述性援引（不含 APA 括号）。"""

    context: str = Field(default="", max_length=4000)


class CitationWeaveOut(BaseModel):
    sentence: str
    citation_id: UUID
    node: dict


class CitationNodeIn(BaseModel):
    evidence_id: UUID | None = None
    mode: str = "parenthetical"
    locator: str | None = None
    prefix: str = ""
    suffix: str = ""


class CitationOccurrenceOut(BaseModel):
    id: UUID
    citation_id: UUID
    evidence_id: UUID | None
    chapter_id: UUID
    chapter_index: int
    chapter_title: str
    node_id: UUID
    cite_mode: str
    locator: str | None
    context_before: str | None
    context_after: str | None
    complete: bool
    citation: CitationOut


class CitationEvidenceOut(BaseModel):
    id: UUID
    citation_id: UUID
    source_file_id: UUID | None
    chunk_id: UUID | None
    page_number: int | None
    paragraph_locator: str | None
    heading_path: list[str] | None
    quote_text: str
    directly_quotable: bool
