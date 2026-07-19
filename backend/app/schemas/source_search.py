"""Schemas for the unified source-search API."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.citation import CitationOut
from app.schemas.project_assistant import SourceOut

SourceType = Literal["paper", "book", "news", "government", "industry_report", "technical", "web"]
SearchScope = Literal["manual", "book", "chapter"]


class SourceCapabilityOut(BaseModel):
    id: SourceType
    label: str
    available: bool
    connectors: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None


class SourceSearchPlanIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    scope: SearchScope = "manual"
    chapter_index: int | None = Field(default=None, ge=1)
    requested_source_types: list[SourceType] = Field(default_factory=list, max_length=7)
    time_from: str | None = Field(default=None, max_length=10)
    time_to: str | None = Field(default=None, max_length=10)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        return value.strip()

    @field_validator("requested_source_types")
    @classmethod
    def unique_source_types(cls, value: list[SourceType]) -> list[SourceType]:
        return list(dict.fromkeys(value))

    @field_validator("time_from", "time_to")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def chapter_scope_requires_index(self) -> SourceSearchPlanIn:
        if self.scope == "chapter" and self.chapter_index is None:
            raise ValueError("chapter_index is required when scope is chapter")
        return self


class SourceSearchIntentOut(BaseModel):
    kind: str
    display_query: str
    person_name: str | None = None
    organization: str | None = None
    topic: str | None = None
    source_types: list[SourceType] = Field(default_factory=list)
    time_from: str | None = None
    time_to: str | None = None
    rationale: str = ""


class SourceSearchPlanOut(BaseModel):
    query: str
    scope: SearchScope = "manual"
    chapter_index: int | None = None
    intent: SourceSearchIntentOut
    queries_by_source: dict[str, str] = Field(default_factory=dict)
    requested_source_types: list[SourceType] = Field(default_factory=list)
    planned_connectors: list[str] = Field(default_factory=list)
    unavailable_source_types: list[SourceType] = Field(default_factory=list)


class SourceSearchIn(SourceSearchPlanIn):
    query: str = Field(default="", max_length=500)
    rows: int = Field(default=25, ge=1, le=50)
    plan: SourceSearchPlanOut | None = None

    @model_validator(mode="after")
    def query_or_plan_required(self) -> SourceSearchIn:
        if not self.query and self.plan is None:
            raise ValueError("query or plan is required")
        return self


class SourceSearchItemOut(BaseModel):
    id: str
    title: str
    url: str = ""
    snippet: str = ""
    authors: list[str] = Field(default_factory=list)
    publisher: str = ""
    published_at: str | None = None
    year: int | None = None
    source_type: SourceType
    provider: str
    domain: str = ""
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    credibility_hint: Literal["high", "medium", "unknown"] = "unknown"
    citeability: bool = False
    metadata_missing: list[str] = Field(default_factory=list)
    document_type: str = ""
    doi: str = ""
    isbn: str = ""
    external_id: str = ""
    journal: str = ""
    citations: int | None = None
    degraded: bool = False


class SourceFacetOut(BaseModel):
    id: SourceType
    label: str
    count: int = 0


class SourceSearchExecutionOut(BaseModel):
    requested_source_types: list[SourceType] = Field(default_factory=list)
    attempted_connectors: list[str] = Field(default_factory=list)
    successful_connectors: list[str] = Field(default_factory=list)
    failed_connectors: dict[str, str] = Field(default_factory=dict)
    unavailable_source_types: list[SourceType] = Field(default_factory=list)
    degraded: bool = False
    duration_ms: int = 0
    result_counts: dict[str, int] = Field(default_factory=dict)


class SourceSearchOut(BaseModel):
    query: str
    plan: SourceSearchPlanOut
    items: list[SourceSearchItemOut] = Field(default_factory=list)
    facets: list[SourceFacetOut] = Field(default_factory=list)
    execution: SourceSearchExecutionOut
    warnings: list[str] = Field(default_factory=list)

    # Compatibility fields retained for one frontend version.
    papers: list[dict[str, Any]] = Field(default_factory=list)
    github: list[dict[str, Any]] = Field(default_factory=list)
    wiki: list[dict[str, Any]] = Field(default_factory=list)
    official_docs: list[dict[str, Any]] = Field(default_factory=list)
    books: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    government: list[dict[str, Any]] = Field(default_factory=list)
    industry_reports: list[dict[str, Any]] = Field(default_factory=list)
    technical: list[dict[str, Any]] = Field(default_factory=list)
    web: list[dict[str, Any]] = Field(default_factory=list)
    refined_queries: list[str] = Field(default_factory=list)
    profile: str = "unified"
    source_hint: str = ""


class SourceSearchResultAddIn(BaseModel):
    target: Literal["source_library", "citation_library"]
    items: list[SourceSearchItemOut] = Field(min_length=1, max_length=50)


class SourceSearchResultAddOut(BaseModel):
    target: Literal["source_library", "citation_library"]
    added_count: int = 0
    sources: list[SourceOut] = Field(default_factory=list)
    citations: list[CitationOut] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
