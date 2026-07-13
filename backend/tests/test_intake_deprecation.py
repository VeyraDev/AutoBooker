"""旧 Intake 写端点统一返回 HTTP 410 Gone。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.intake import CreationOrigin, IntakeItemType
from app.routers.intake import (
    IntakeInitIn,
    IntakeItemIn,
    UnderstandingPatchIn,
    WritingPlanPatchIn,
    _deprecated_intake_write,
    add_intake_item,
    confirm_understanding,
    confirm_writing_plan,
    generate_understanding,
    generate_writing_plan,
    init_intake,
    patch_understanding,
    patch_writing_plan,
    upload_intake_item,
)


def _user():
    return SimpleNamespace(id=uuid4())


def _db():
    return object()


def test_deprecated_guard_returns_410():
    with pytest.raises(HTTPException) as exc:
        _deprecated_intake_write()
    assert exc.value.status_code == 410
    assert "项目启动助手" in str(exc.value.detail)


@pytest.mark.parametrize(
    "handler,kwargs",
    [
        (init_intake, {"book_id": uuid4(), "body": IntakeInitIn(creation_origin=CreationOrigin.idea_only)}),
        (add_intake_item, {"book_id": uuid4(), "body": IntakeItemIn(item_type=IntakeItemType.natural_text, text_content="hi")}),
        (generate_understanding, {"book_id": uuid4()}),
        (patch_understanding, {"book_id": uuid4(), "body": UnderstandingPatchIn(correction="fix")}),
        (confirm_understanding, {"book_id": uuid4()}),
        (generate_writing_plan, {"book_id": uuid4()}),
        (patch_writing_plan, {"book_id": uuid4(), "body": WritingPlanPatchIn(user_facing_text="plan")}),
        (confirm_writing_plan, {"book_id": uuid4()}),
    ],
)
def test_deprecated_intake_sync_handlers_return_410(handler, kwargs):
    kwargs["user"] = _user()
    kwargs["db"] = _db()
    with pytest.raises(HTTPException) as exc:
        handler(**kwargs)
    assert exc.value.status_code == 410


def test_upload_intake_item_returns_410():
    file = type("F", (), {"filename": "a.txt", "read": staticmethod(lambda: b"x")})()

    async def _call():
        await upload_intake_item(book_id=uuid4(), file=file, user=_user(), db=_db())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_call())
    assert exc.value.status_code == 410
