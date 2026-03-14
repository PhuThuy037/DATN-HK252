from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlmodel import Session

from app.conversation.model import Conversation
from app.permissions.core import AuthContext, forbid, not_found
from app.permissions.loaders.conversation import (
    load_conversation_or_404,
    load_rule_set_owner_active_or_403,
)
from app.permissions.policies.conversation import ConversationPolicy


@dataclass(slots=True)
class ConversationAccess:
    ctx: AuthContext
    conversation: Conversation


_RULE_SET_OWNER = "rule_set_owner"


class ConversationGuard:
    def build_ctx(
        self, *, session: Session, conversation_id: UUID, user_id: UUID
    ) -> tuple[AuthContext, Conversation]:
        c = load_conversation_or_404(session=session, conversation_id=conversation_id)

        # Personal: owner-only
        if c.company_id is None:
            if c.user_id != user_id:
                raise not_found(
                    "Conversation not found",
                    field="conversation_id",
                    reason="not_owner",
                )
            # Personal owner is treated as rule_set_owner for unified checks.
            ctx = AuthContext(user_id=user_id, role=_RULE_SET_OWNER, rule_set_id=None)
            return ctx, c

        # Rule-set conversation: require active owner mapping.
        load_rule_set_owner_active_or_403(
            session=session, rule_set_id=c.company_id, user_id=user_id
        )
        ctx = AuthContext(
            user_id=user_id,
            role=_RULE_SET_OWNER,
            rule_set_id=c.company_id,
        )
        return ctx, c

    def require_view(
        self, *, session: Session, conversation_id: UUID, user_id: UUID
    ) -> ConversationAccess:
        ctx, c = self.build_ctx(
            session=session, conversation_id=conversation_id, user_id=user_id
        )
        if not ConversationPolicy.can_view(ctx):
            raise forbid("Not allowed to view conversation")
        return ConversationAccess(ctx=ctx, conversation=c)

    def require_update(
        self, *, session: Session, conversation_id: UUID, user_id: UUID
    ) -> ConversationAccess:
        ctx, c = self.build_ctx(
            session=session, conversation_id=conversation_id, user_id=user_id
        )
        if not ConversationPolicy.can_update(ctx, owner_user_id=c.user_id):
            raise forbid("Not allowed to update conversation")
        return ConversationAccess(ctx=ctx, conversation=c)

    def require_delete(
        self, *, session: Session, conversation_id: UUID, user_id: UUID
    ) -> ConversationAccess:
        ctx, c = self.build_ctx(
            session=session, conversation_id=conversation_id, user_id=user_id
        )
        if not ConversationPolicy.can_delete(ctx, owner_user_id=c.user_id):
            raise forbid("Not allowed to delete conversation")
        return ConversationAccess(ctx=ctx, conversation=c)
