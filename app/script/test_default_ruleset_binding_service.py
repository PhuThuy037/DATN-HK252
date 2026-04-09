from __future__ import annotations

import os
import time

import app.db.all_models  # noqa: F401
from sqlmodel import Session, select

from app.auth.model import User
from app.auth.passwords import hash_password
from app.common.enums import SystemRole, UserStatus
from app.common.errors import AppError
from app.company import service as company_service
from app.conversation import service as convo_service
from app.core.config import get_settings
from app.db.engine import engine


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _create_user(
    session: Session,
    *,
    email: str,
    role: SystemRole,
    name: str,
) -> User:
    row = User(
        email=email.strip().lower(),
        hashed_password=hash_password("123456"),
        name=name,
        status=UserStatus.active,
        role=role,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _set_default_admin_email(value: str | None) -> str | None:
    previous = os.environ.get("DEFAULT_RULESET_ADMIN_EMAIL")
    if value is None:
        os.environ.pop("DEFAULT_RULESET_ADMIN_EMAIL", None)
    else:
        os.environ["DEFAULT_RULESET_ADMIN_EMAIL"] = value
    get_settings.cache_clear()
    return previous


def _restore_default_admin_email(value: str | None) -> None:
    if value is None:
        os.environ.pop("DEFAULT_RULESET_ADMIN_EMAIL", None)
    else:
        os.environ["DEFAULT_RULESET_ADMIN_EMAIL"] = value
    get_settings.cache_clear()


def _expect_internal_error(exc: AppError, reason: str) -> None:
    if exc.status_code != 500:
        fail(f"expected status_code=500, got {exc.status_code}: {exc.message}")
    details = list(exc.details or [])
    reasons = {str(item.get('reason') or '') for item in details if isinstance(item, dict)}
    if reason not in reasons:
        fail(f"expected reason={reason}, got details={details}")


def main() -> None:
    previous_email = os.environ.get("DEFAULT_RULESET_ADMIN_EMAIL")
    now = int(time.time())

    try:
        with Session(engine) as session:
            print("[1/5] setup admin with active rule set and regular user")
            admin = _create_user(
                session,
                email=f"default.ruleset.admin.{now}@test.com",
                role=SystemRole.admin,
                name="Default Rule Source Admin",
            )
            regular = _create_user(
                session,
                email=f"default.ruleset.user.{now}@test.com",
                role=SystemRole.user,
                name="Default Rule Source User",
            )
            company, _ = company_service.create_company(
                session=session,
                user_id=admin.id,
                name=f"Default Rule Source {now}",
            )

            print("[2/5] blank config fails clearly")
            _set_default_admin_email("")
            try:
                convo_service.create_personal_conversation(
                    session=session,
                    user_id=regular.id,
                    title="Blank config",
                )
                fail("expected blank config to fail")
            except AppError as exc:
                _expect_internal_error(exc, "missing_config")

            print("[3/5] unknown admin email fails clearly")
            _set_default_admin_email(f"missing.default.ruleset.{now}@test.com")
            try:
                convo_service.create_personal_conversation(
                    session=session,
                    user_id=regular.id,
                    title="Unknown admin",
                )
                fail("expected unknown admin email to fail")
            except AppError as exc:
                _expect_internal_error(exc, "user_not_found")

            print("[4/5] admin without active rule set fails clearly")
            no_rule_admin = _create_user(
                session,
                email=f"default.ruleset.norules.{now}@test.com",
                role=SystemRole.admin,
                name="No Rule Set Admin",
            )
            _set_default_admin_email(no_rule_admin.email)
            try:
                convo_service.create_personal_conversation(
                    session=session,
                    user_id=regular.id,
                    title="No active rule set",
                )
                fail("expected admin without active rule set to fail")
            except AppError as exc:
                _expect_internal_error(exc, "active_rule_set_missing")

            print("[5/5] happy path binds personal conversation to default rule set")
            _set_default_admin_email(admin.email)
            conversation = convo_service.create_personal_conversation(
                session=session,
                user_id=regular.id,
                title="Bound personal conversation",
            )
            if str(conversation.user_id) != str(regular.id):
                fail(
                    f"conversation owner mismatch: expected={regular.id}, got={conversation.user_id}"
                )
            if str(conversation.company_id) != str(company.id):
                fail(
                    f"default rule set binding mismatch: expected={company.id}, got={conversation.company_id}"
                )

            refreshed = session.exec(
                select(User).where(User.id == regular.id)
            ).first()
            if refreshed is None:
                fail("regular user should still exist")

        print("ALL PASS: default rule set binding service checks are good.")
    finally:
        _restore_default_admin_email(previous_email)


if __name__ == "__main__":
    main()
