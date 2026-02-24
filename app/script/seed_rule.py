from uuid import UUID
from sqlmodel import Session

from app.db.engine import engine  # <-- đổi đúng đường dẫn engine của mày
from app.rule.seed import RuleSeeder
import app.db.all_models  # noqa: F401

SEED_PATH = "app/config/seed_rules.yaml"  # hoặc app/rule/seed_rules.yaml nếu mày để đó
SYSTEM_USER_ID = UUID("cd523d42-bec2-4a66-addc-dd7004aa7f4f")  # user id test của mày


def main():
    seeder = RuleSeeder(SEED_PATH)
    with Session(engine) as session:
        n = seeder.upsert_global_rules(
            session=session, created_by_user_id=SYSTEM_USER_ID
        )
        print(f"✅ Seeded/updated {n} rules from {SEED_PATH}")


if __name__ == "__main__":
    main()