from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ParseStatusOut(str, Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class ReferenceFileOut(BaseModel):
    id: UUID
    book_id: UUID
    filename: str
    file_type: str
    ingest_kind: str = "reference"
    file_purposes: list[str] | None = None
    outline_usage: str | None = None
    user_note: str | None = None
    parse_status: ParseStatusOut
    error_message: str | None
    parsed_at: datetime | None
    created_at: datetime
    chunk_count: int = 0
    lifecycle_status: str = "processing"
    parse_artifacts: dict | None = None
    conflicts: list[dict] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ReferenceUploadOut(BaseModel):
    id: UUID
    filename: str
    file_type: str
    ingest_kind: str = "reference"
    parse_status: ParseStatusOut
    message: str = "uploaded, parsing in background"
    lifecycle_status: str = "processing"


class ReferenceConfirmIn(BaseModel):
    purposes: list[str] | None = None
    primary_outline: bool | None = None
    conflict_resolutions: dict[str, str] = Field(default_factory=dict)


class ReferenceSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)


class ReferenceSearchHit(BaseModel):
    content: str
    filename: str


class ReferenceSearchOut(BaseModel):
    snippets: list[str]
    hits: list[ReferenceSearchHit] = Field(default_factory=list)
