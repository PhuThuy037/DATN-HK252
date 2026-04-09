from __future__ import annotations

from app.permissions.core import AuthContext

_CONVERSATION_OWNER = "conversation_owner"
_SYSTEM_ADMIN = "system_admin"


class ConversationPolicy:
    @staticmethod
    def can_view(ctx: AuthContext) -> bool:
        return ctx.role in {_CONVERSATION_OWNER, _SYSTEM_ADMIN}

    @staticmethod
    def can_update(ctx: AuthContext, *, owner_user_id) -> bool:
        return ctx.role == _CONVERSATION_OWNER

    @staticmethod
    def can_delete(ctx: AuthContext, *, owner_user_id) -> bool:
        return ctx.role == _CONVERSATION_OWNER
