from uuid import UUID
from sqlmodel import Session, select

from app.db.engine import engine
from app.auth.model import User
from app.rule.seed import RuleSeeder
import app.db.all_models  # noqa: F401

SEED_PATH = "app/config/seed_rules.yaml"
PREFERRED_USER_ID = UUID("cd523d42-bec2-4a66-addc-dd7004aa7f4f")


def resolve_created_by(session: Session) -> UUID:
    u = session.get(User, PREFERRED_USER_ID)
    if u:
        return u.id

    u = session.exec(select(User).order_by(User.created_at.asc())).first()
    if not u:
        raise RuntimeError("No users in DB. Create a user first, then seed rules.")
    return u.id


def main():
    seeder = RuleSeeder(SEED_PATH)
    with Session(engine) as session:
        created_by = resolve_created_by(session)
        n = seeder.upsert_global_rules(session=session, created_by_user_id=created_by)
        print(f"✅ Seeded/updated {n} rules (created_by={created_by}) from {SEED_PATH}")


if __name__ == "__main__":
    main()