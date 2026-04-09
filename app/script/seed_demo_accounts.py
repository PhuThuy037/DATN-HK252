from __future__ import annotations

import os

from sqlmodel import Session, select

import app.db.all_models  # noqa: F401
from app.auth.model import User
from app.auth.passwords import hash_password
from app.common.enums import SystemRole, UserStatus
from app.db.engine import engine


DEMO_ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "demo-admin@datn.local").strip().lower()
DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "123456")
DEMO_ADMIN_NAME = os.getenv("DEMO_ADMIN_NAME", "Demo Admin").strip() or "Demo Admin"

DEMO_USER_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo-user@datn.local").strip().lower()
DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "123456")
DEMO_USER_NAME = os.getenv("DEMO_USER_NAME", "Demo User").strip() or "Demo User"


def _upsert_user(
    session: Session,
    *,
    email: str,
    password: str,
    name: str,
    role: SystemRole,
) -> User:
    row = session.exec(select(User).where(User.email == email)).first()
    if row is None:
        row = User(
            email=email,
            hashed_password=hash_password(password),
            name=name,
            status=UserStatus.active,
            role=role,
        )
    else:
        row.name = name
        row.status = UserStatus.active
        row.role = role
        if password:
            row.hashed_password = hash_password(password)

    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def main() -> None:
    with Session(engine) as session:
        admin = _upsert_user(
            session,
            email=DEMO_ADMIN_EMAIL,
            password=DEMO_ADMIN_PASSWORD,
            name=DEMO_ADMIN_NAME,
            role=SystemRole.admin,
        )
        user = _upsert_user(
            session,
            email=DEMO_USER_EMAIL,
            password=DEMO_USER_PASSWORD,
            name=DEMO_USER_NAME,
            role=SystemRole.user,
        )

    print(
        "[seed_demo_accounts] admin="
        f"{admin.email} role={admin.role.value} password={DEMO_ADMIN_PASSWORD}"
    )
    print(
        "[seed_demo_accounts] user="
        f"{user.email} role={user.role.value} password={DEMO_USER_PASSWORD}"
    )


if __name__ == "__main__":
    main()
