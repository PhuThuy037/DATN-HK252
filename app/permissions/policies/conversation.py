from __future__ import annotations

from app.common.enums import MemberRole
from app.permissions.core import AuthContext


class ConversationPolicy:
    @staticmethod
    def can_view(ctx: AuthContext) -> bool:
        return ctx.role == MemberRole.company_admin

    @staticmethod
    def can_update(ctx: AuthContext, *, owner_user_id) -> bool:
        return ctx.role == MemberRole.company_admin

    @staticmethod
    def can_delete(ctx: AuthContext, *, owner_user_id) -> bool:
        return ctx.role == MemberRole.company_admin
