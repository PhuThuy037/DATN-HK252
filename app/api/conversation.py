from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.conversation.schemas import (
    ConversationCreatePersonalIn,
    ConversationCreateCompanyIn,
    ConversationOut,
    MessageCreateIn,
    MessageOut,
)
from app.conversation import service as convo_service
from app.permissions.deps.conversation import ConversationView
from app.common.schemas import ApiResponse

router = APIRouter(prefix="/v1", tags=["conversations"])


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
    return ApiResponse(ok=True, data=c)


@router.post(
    "/companies/{company_id}/conversations", response_model=ApiResponse[ConversationOut]
)
def create_company_conversation(
    company_id: UUID,
    payload: ConversationCreateCompanyIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    c = convo_service.create_company_conversation(
        session=session,
        user_id=principal.user_id,
        company_id=company_id,
        title=payload.title,
        model_name=payload.model_name,
        temperature=payload.temperature,
    )
    return ApiResponse(ok=True, data=c)


@router.post(
    "/conversations/{conversation_id}/messages", response_model=ApiResponse[MessageOut]
)
def send_message(
    conversation_id: UUID,
    payload: MessageCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
    access: ConversationView,  # ✅ ensures user can view/send in this conversation
):
    # access.conversation already loaded by guard; ensure same id
    msg = convo_service.append_user_message(
        session=session,
        conversation_id=conversation_id,
        user_id=principal.user_id,
        content=payload.content,
        input_type=payload.input_type,
    )
    return ApiResponse(ok=True, data=msg)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[list[MessageOut]],
)
def get_messages(
    conversation_id: UUID,
    session: SessionDep,
    access: ConversationView,
):
    items = convo_service.list_messages(
        session=session, conversation_id=conversation_id
    )
    return ApiResponse(ok=True, data=items)