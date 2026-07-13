from typing import TypeVar

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


async def parse_json_body(request: Request, model: type[T]) -> T:
    """Parse JSON body even when Content-Type is missing (e.g. dev proxy)."""
    raw = await request.body()
    if not raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Request body is required")
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.errors()) from exc
