from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str | None = None
    payload_json: dict | None = None
    is_read: bool
    created_at: str | None = None

    model_config = {"from_attributes": True}


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int


class FeedbackIn(BaseModel):
    type: str = "other"
    content: str = Field(..., min_length=5, max_length=4000)
    page_url: str | None = None
    book_id: str | None = None


class FeedbackOut(BaseModel):
    id: str
    type: str
    status: str
    content: str
    reply: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
