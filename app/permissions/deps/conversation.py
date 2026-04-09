from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.auth.deps import CurrentUser
from app.api.deps import SessionDep
from app.permissions.guards.conversation_guard import (
    ConversationGuard,
    ConversationAccess,
)

_guard = ConversationGuard()


def require_conversation_view(
    conversation_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationAccess:
    return _guard.require_view(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        system_role=current_user.role,
    )


def require_conversation_update(
    conversation_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationAccess:
    return _guard.require_update(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        system_role=current_user.role,
    )


def require_conversation_delete(
    conversation_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationAccess:
    return _guard.require_delete(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.id,
        system_role=current_user.role,
    )


ConversationView = Annotated[ConversationAccess, Depends(require_conversation_view)]
ConversationUpdate = Annotated[ConversationAccess, Depends(require_conversation_update)]
ConversationDelete = Annotated[ConversationAccess, Depends(require_conversation_delete)]
