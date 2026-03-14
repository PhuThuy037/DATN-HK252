from __future__ import annotations

from app.permissions.core import AuthContext

_RULE_SET_OWNER = "rule_set_owner"


class ConversationPolicy:
    @staticmethod
    def can_view(ctx: AuthContext) -> bool:
        return ctx.role == _RULE_SET_OWNER

    @staticmethod
    def can_update(ctx: AuthContext, *, owner_user_id) -> bool:
        return ctx.role == _RULE_SET_OWNER

    @staticmethod
    def can_delete(ctx: AuthContext, *, owner_user_id) -> bool:
        return ctx.role == _RULE_SET_OWNER
