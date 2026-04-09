import os

from sqlmodel import Session, select

from app.db.engine import engine
from app.auth.passwords import hash_password
from app.auth.model import User
from app.common.enums import SystemRole, UserStatus
from app.rule.seed import RuleSeeder
import app.db.all_models  # noqa: F401

SEED_PATH = "app/config/seed_rules.yaml"
PREFERRED_USER_EMAIL = os.getenv("SEED_RULE_CREATED_BY_EMAIL", "").strip().lower()
AUTO_CREATE_USER = (
    os.getenv("SEED_RULE_AUTO_CREATE_USER", "true").strip().lower() in {"1", "true", "yes"}
)
SEED_USER_EMAIL = os.getenv("SEED_RULE_USER_EMAIL", "seed-admin@datn.local").strip().lower()
SEED_USER_PASSWORD = os.getenv("SEED_RULE_USER_PASSWORD", "123456")
SEED_USER_NAME = os.getenv("SEED_RULE_USER_NAME", "Seed Admin").strip() or "Seed Admin"


def _find_user_by_email(session: Session, email: str) -> User | None:
    normalized = (email or "").strip().lower()
    if not normalized:
        return None
    return session.exec(select(User).where(User.email == normalized)).first()


def _create_seed_user(session: Session) -> User:
    existing = _find_user_by_email(session, SEED_USER_EMAIL)
    if existing:
        return existing

    u = User(
        email=SEED_USER_EMAIL,
        hashed_password=hash_password(SEED_USER_PASSWORD),
        name=SEED_USER_NAME,
        status=UserStatus.active,
        role=SystemRole.admin,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def resolve_created_by(session: Session):
    if PREFERRED_USER_EMAIL:
        u = _find_user_by_email(session, PREFERRED_USER_EMAIL)
        if u:
            return u.id

    u = session.exec(
        select(User)
        .where(User.status == UserStatus.active)
        .order_by(User.created_at.asc())
    ).first()
    if not u:
        if AUTO_CREATE_USER:
            u = _create_seed_user(session)
        else:
            raise RuntimeError(
                "No active users found. "
                "Set SEED_RULE_CREATED_BY_EMAIL or enable SEED_RULE_AUTO_CREATE_USER=true."
            )
    return u.id


def main():
    seeder = RuleSeeder(SEED_PATH)
    with Session(engine) as session:
        created_by = resolve_created_by(session)
        n = seeder.upsert_global_rules(session=session, created_by_user_id=created_by)
        print(f"✅ Seeded/updated {n} rules (created_by={created_by}) from {SEED_PATH}")


if __name__ == "__main__":
    main()
