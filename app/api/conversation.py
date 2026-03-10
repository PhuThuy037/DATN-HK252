from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.enums import RuleAction
from app.common.schemas import ApiResponse
from app.conversation import service as convo_service
from app.conversation.schemas import (
    ConversationCreatePersonalIn,
    ConversationCreateRuleSetIn,
    ConversationOut,
    MessageCreateIn,
    MessagePublicOut,
    MessagesPageMeta,
    MessagesPageOut,
    SendMessageOut,
)
from app.permissions.deps.conversation import ConversationView

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
    c = convo_service.create_company_conversation(
        session=session,
        user_id=principal.user_id,
        company_id=rule_set_id,
        title=payload.title,
        model_name=payload.model_name,
        temperature=payload.temperature,
    )
    return ApiResponse(ok=True, data=_conversation_out(c))


@router.post(
    "/conversations/{conversation_id}/messages", response_model=ApiResponse[SendMessageOut]
)
async def send_message(
    conversation_id: UUID,
    payload: MessageCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
    access: ConversationView,
):
    msg, assistant_message_id = await convo_service.append_user_message_async(
        session=session,
        conversation_id=conversation_id,
        user_id=principal.user_id,
        content=payload.content,
        input_type=payload.input_type,
    )
    out = SendMessageOut.model_validate(msg).model_copy(
        update={"assistant_message_id": assistant_message_id}
    )

    if msg.final_action == RuleAction.block:
        return ApiResponse(ok=False, data=out, error=None)

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

