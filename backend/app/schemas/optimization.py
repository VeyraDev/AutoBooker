from uuid import UUID

from pydantic import BaseModel, Field


class OptimizationSettingsIn(BaseModel):
    allow_structure_changes: bool = False
    optimization_goals: list[str] = Field(default_factory=list, max_length=20)


class MappingPatch(BaseModel):
    baseline_chapter_id: UUID
    outline_chapter_index: int | None = None
    outline_title: str | None = None
    confirmed: bool = True


class MappingConfirmIn(BaseModel):
    mappings: list[MappingPatch] = Field(default_factory=list)


class OptimizeChapterIn(BaseModel):
    baseline_chapter_id: UUID
    instruction: str = Field(default="", max_length=4000)


class RevisionDecisionIn(BaseModel):
    action: str


class OptimizationProjectOut(BaseModel):
    id: UUID
    book_id: UUID
    source_file_id: UUID
    status: str
    allow_structure_changes: bool
    optimization_goals: list[str]
    diagnosis: dict | None = None
    optimization_plan: dict | None = None
    baseline_chapters: list[dict] = Field(default_factory=list)
    mappings: list[dict] = Field(default_factory=list)
    revisions: list[dict] = Field(default_factory=list)
    error_message: str | None = None
