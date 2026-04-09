from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.enums import ConversationStatus, RuleAction
from app.common.schemas import ApiResponse
from app.conversation import service as convo_service
from app.conversation.schemas import (
    ConversationDeleteOut,
    ConversationListItemOut,
    ConversationCreatePersonalIn,
    ConversationCreateRuleSetIn,
    ConversationOut,
    ConversationsPageMeta,
    ConversationsPageOut,
    ConversationUpdateIn,
    MessageCreateIn,
    MessageDetailOut,
    MessagePublicOut,
    MessagesPageMeta,
    MessagesPageOut,
    SendMessageOut,
)
from app.permissions.deps.conversation import (
    ConversationDelete,
    ConversationUpdate,
    ConversationView,
)

router = APIRouter(prefix="/v1", tags=["conversations"])


def _conversation_out(c) -> ConversationOut:
    return ConversationOut(
        id=c.id,
        user_id=c.user_id,
        rule_set_id=c.company_id,
        title=c.title,
        model_name=c.model_name,
        temperature=c.temperature,
        last_sequence_number=c.last_sequence_number,
        status=(c.status.value if hasattr(c.status, "value") else str(c.status)),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/conversations", response_model=ApiResponse[ConversationsPageOut])
def list_conversations(
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=20, ge=1, le=50),
    before_updated_at: datetime | None = Query(default=None),
    before_id: UUID | None = Query(default=None),
    status: ConversationStatus | None = Query(default=ConversationStatus.active),
):
    rows, has_more, next_before_updated_at, next_before_id = (
        convo_service.list_conversations_page(
            session=session,
            user_id=principal.user_id,
            limit=limit,
            before_updated_at=before_updated_at,
            before_id=before_id,
            status=status,
        )
    )

    items: list[ConversationListItemOut] = []
    for c in rows:
        last_message_at, last_message_preview = convo_service.get_last_message_summary(
            session=session,
            conversation_id=c.id,
        )
        items.append(
            ConversationListItemOut(
                id=c.id,
                rule_set_id=c.company_id,
                title=c.title,
                status=(c.status.value if hasattr(c.status, "value") else str(c.status)),
                model_name=c.model_name,
                temperature=c.temperature,
                last_sequence_number=c.last_sequence_number,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_message_at=last_message_at,
                last_message_preview=last_message_preview,
            )
        )

    return ApiResponse(
        ok=True,
        data=ConversationsPageOut(
            items=items,
            page=ConversationsPageMeta(
                limit=limit,
                has_more=has_more,
                next_before_updated_at=next_before_updated_at,
                next_before_id=next_before_id,
                status=(status.value if status is not None else None),
            ),
        ),
    )


@router.post("/conversations/personal", response_model=ApiResponse[ConversationOut])
def create_personal_conversation(
    payload: ConversationCreatePersonalIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    c = convo_service.create_personal_conversation(
        session=session,
        user_id=principal.user_id,
        title=payload.title,
        model_name=payload.model_name,
        temperature=payload.temperature,
    )
    return ApiResponse(ok=True, data=_conversation_out(c))


@router.post(
    "/rule-sets/{rule_set_id}/conversations", response_model=ApiResponse[ConversationOut]
)
def create_rule_set_conversation(
    rule_set_id: UUID,
    payload: ConversationCreateRuleSetIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    c = convo_service.create_rule_set_conversation(
        session=session,
        user_id=principal.user_id,
        rule_set_id=rule_set_id,
        title=payload.title,
        model_name=payload.model_name,
        temperature=payload.temperature,
    )
    return ApiResponse(ok=True, data=_conversation_out(c))


@router.get("/conversations/{conversation_id}", response_model=ApiResponse[ConversationOut])
def get_conversation_detail(
    conversation_id: UUID,
    session: SessionDep,
    access: ConversationView,
):
    c = convo_service.get_active_conversation_or_404(
        session=session,
        conversation_id=conversation_id,
    )
    return ApiResponse(ok=True, data=_conversation_out(c))


@router.patch("/conversations/{conversation_id}", response_model=ApiResponse[ConversationOut])
def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdateIn,
    session: SessionDep,
    access: ConversationUpdate,
):
    c = convo_service.update_conversation_metadata(
        session=session,
        conversation_id=conversation_id,
        title=payload.title,
        status=payload.status,
        fields_set=set(payload.model_fields_set),
    )
    return ApiResponse(ok=True, data=_conversation_out(c))


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[ConversationDeleteOut],
)
def delete_conversation(
    conversation_id: UUID,
    session: SessionDep,
    access: ConversationDelete,
):
    c = convo_service.soft_delete_conversation(
        session=session,
        conversation_id=conversation_id,
    )
    return ApiResponse(
        ok=True,
        data=ConversationDeleteOut(
            id=c.id,
            status=(c.status.value if hasattr(c.status, "value") else str(c.status)),
        ),
    )


@router.post(
    "/conversations/{conversation_id}/messages", response_model=ApiResponse[SendMessageOut]
)
async def send_message(
    conversation_id: UUID,
    payload: MessageCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
    access: ConversationUpdate,
):
    msg, assistant_message_id = await convo_service.append_user_message_async(
        session=session,
        conversation_id=conversation_id,
        user_id=principal.user_id,
        content=payload.content,
        input_type=payload.input_type,
    )
    out = SendMessageOut.model_validate(
        convo_service.build_safe_message_detail(message=msg)
    ).model_copy(
        update={"assistant_message_id": assistant_message_id}
    )

    if msg.final_action == RuleAction.block:
        return ApiResponse(ok=False, data=out, error=None)

    return ApiResponse(ok=True, data=out)


@router.get(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=ApiResponse[MessageDetailOut],
)
def get_message_detail(
    conversation_id: UUID,
    message_id: UUID,
    session: SessionDep,
    access: ConversationView,
):
    row = convo_service.get_message_for_conversation_or_404(
        session=session,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    out = MessageDetailOut.model_validate(
        convo_service.build_safe_message_detail(message=row)
    )
    return ApiResponse(ok=True, data=out)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[MessagesPageOut],
)
def get_messages(
    conversation_id: UUID,
    session: SessionDep,
    access: ConversationView,
    limit: int = Query(default=20, ge=1, le=50),
    before_seq: int | None = Query(default=None, ge=1),
):
    items, has_more, next_before_seq, oldest_seq, newest_seq = (
        convo_service.list_messages_page(
            session=session,
            conversation_id=conversation_id,
            limit=limit,
            before_seq=before_seq,
        )
    )

    out: list[MessagePublicOut] = []
    for m in items:
        is_blocked = m.final_action == RuleAction.block
        is_masked = m.final_action == RuleAction.mask

        if is_blocked:
            safe_content = None
            state = "blocked"
        elif m.content_masked is not None:
            safe_content = m.content_masked
            state = "masked"
        elif is_masked:
            # Fail-safe: if action says MASK but masked text is missing, do not expose raw.
            safe_content = None
            state = "masked"
        else:
            safe_content = m.content
            state = "normal"

        out.append(
            MessagePublicOut(
                id=m.id,
                role=m.role,
                content=safe_content,
                created_at=m.created_at,
                state=state,
            )
        )

    return ApiResponse(
        ok=True,
        data=MessagesPageOut(
            items=out,
            page=MessagesPageMeta(
                limit=limit,
                has_more=has_more,
                next_before_seq=next_before_seq,
                oldest_seq=oldest_seq,
                newest_seq=newest_seq,
            ),
        ),
    )

