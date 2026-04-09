from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.admin_monitoring import service as admin_service
from app.admin_monitoring.schemas import (
    AdminAuditLogOut,
    AdminBlockMaskLogOut,
    AdminConversationDetailOut,
    AdminConversationListItemOut,
    AdminConversationMessagesPageOut,
    AdminRagRetrievalLogOut,
)
from app.api.deps import SessionDep
from app.auth.deps import require_admin
from app.common.enums import ConversationStatus
from app.common.schemas import ApiResponse, Meta
from app.conversation.schemas import MessageDetailOut, MessagesPageMeta

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin-monitoring"],
    dependencies=[Depends(require_admin)],
)


@router.get(
    "/conversations",
    response_model=ApiResponse[list[AdminConversationListItemOut]],
)
def list_admin_conversations(
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    status: ConversationStatus | None = Query(default=None),
    q: str | None = Query(default=None),
):
    rows, next_cursor, has_more, total = admin_service.list_admin_conversations_paginated(
        session=session,
        limit=limit,
        cursor=cursor,
        status=status,
        q=q,
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[AdminConversationDetailOut],
)
def get_admin_conversation_detail(
    conversation_id: UUID,
    session: SessionDep,
):
    row = admin_service.get_admin_conversation_detail(
        session=session,
        conversation_id=conversation_id,
    )
    return ApiResponse(ok=True, data=row)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[AdminConversationMessagesPageOut],
)
def list_admin_conversation_messages(
    conversation_id: UUID,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    before_seq: int | None = Query(default=None, ge=1),
):
    items, has_more, next_before_seq, oldest_seq, newest_seq = (
        admin_service.list_admin_conversation_messages_page(
            session=session,
            conversation_id=conversation_id,
            limit=limit,
            before_seq=before_seq,
        )
    )
    return ApiResponse(
        ok=True,
        data=AdminConversationMessagesPageOut(
            items=[MessageDetailOut.model_validate(item) for item in items],
            page=MessagesPageMeta(
                limit=limit,
                has_more=has_more,
                next_before_seq=next_before_seq,
                oldest_seq=oldest_seq,
                newest_seq=newest_seq,
            ),
        ),
    )


@router.get(
    "/logs/block-mask",
    response_model=ApiResponse[list[AdminBlockMaskLogOut]],
)
def list_admin_block_mask_logs(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    action: Literal["mask", "block"] | None = Query(default=None),
):
    rows, next_cursor, has_more, total = admin_service.list_admin_block_mask_logs_paginated(
        session=session,
        limit=limit,
        cursor=cursor,
        action=action,
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )


@router.get(
    "/logs/rag-retrieval",
    response_model=ApiResponse[list[AdminRagRetrievalLogOut]],
)
def list_admin_rag_retrieval_logs(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
):
    rows, next_cursor, has_more, total = (
        admin_service.list_admin_rag_retrieval_logs_paginated(
            session=session,
            limit=limit,
            cursor=cursor,
        )
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )


@router.get(
    "/logs/audit",
    response_model=ApiResponse[list[AdminAuditLogOut]],
)
def list_admin_audit_logs(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
):
    rows, next_cursor, has_more, total = admin_service.list_admin_audit_logs_paginated(
        session=session,
        limit=limit,
        cursor=cursor,
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )
