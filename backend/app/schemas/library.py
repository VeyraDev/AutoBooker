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


class LibraryCategoryOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    sort_order: int = 0


class LibraryItemOut(BaseModel):
    id: str
    title: str
    authors: list[str] = []
    description: str | None = None
    category_id: str | None = None
    category_slug: str | None = None
    category_name: str | None = None
    tags: list[str] = []
    language: str | None = None
    file_type: str
    filename: str
    size_bytes: int
    uploader_name: str | None = None
    use_count: int = 0
    created_at: str | None = None
    is_mine: bool = False


class LibraryItemListOut(BaseModel):
    items: list[LibraryItemOut]
    total: int
    categories: list[LibraryCategoryOut] = Field(default_factory=list)


class LibraryItemUploadOut(BaseModel):
    item: LibraryItemOut


class AddShelfToBookIn(BaseModel):
    item_id: str
