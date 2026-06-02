from pydantic import BaseModel, Field


class GlobalLiteratureOut(BaseModel):
    id: str
    source: str
    title: str
    authors: list[str] = []
    year: int | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    tags: list[str] = []
    contributor_name: str | None = None
    cite_count: int = 0

    model_config = {"from_attributes": True}


class GlobalLiteratureListOut(BaseModel):
    items: list[GlobalLiteratureOut]
    total: int


class AddToBookIn(BaseModel):
    literature_id: str
