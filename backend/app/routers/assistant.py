"""Unified AI assistant endpoint."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.assistant import AssistantRequestIn
from app.services import book_service
from app.services.assistant.handler import handle_assistant_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["assistant"])


@router.post("/{book_id}/chapters/{chapter_index}/assistant")
async def assistant(
    book_id: UUID,
    chapter_index: int,
    body: AssistantRequestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    try:
        result = await handle_assistant_request(
            user_text=body.user_text,
            selected_text=body.selected_text,
            figure_id=body.figure_id,
            cursor_paragraph=body.cursor_paragraph,
            explicit_intent=body.explicit_intent,
            book_id=book_id,
            chapter_index=chapter_index,
            db=db,
            chart_type=body.chart_type,
            sub_kind=body.sub_kind,
        )
    except ValueError as e:
        logger.warning("assistant 400 book=%s ch=%s: %s", book_id, chapter_index, e)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except RuntimeError as e:
        logger.error(
            "assistant 502 book=%s ch=%s intent=%s: %s",
            book_id,
            chapter_index,
            body.explicit_intent,
            e,
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    except Exception as e:
        from openai import APIConnectionError, APITimeoutError

        if isinstance(e, (APITimeoutError, APIConnectionError)):
            logger.error(
                "assistant 502 book=%s ch=%s intent=%s: %s",
                book_id,
                chapter_index,
                body.explicit_intent,
                e,
            )
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "OpenAI 图像服务连接超时。可配置代理、增大 OPENAI_IMAGE_TIMEOUT_SEC，"
                "或设置 FIGURE_IMAGE_PROVIDER=wanx / 确保 FIGURE_IMAGE_FALLBACK_WANX=true。",
            ) from e
        logger.exception(
            "assistant 500 book=%s ch=%s intent=%s",
            book_id,
            chapter_index,
            body.explicit_intent,
        )
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"助手处理失败: {e}") from e
    return result
