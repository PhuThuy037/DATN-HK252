from __future__ import annotations

import argparse

from sqlmodel import Session, select

from app.db.engine import engine
from app.rule.model import Rule
from app.rule_embedding.service import backfill_rule_embeddings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill rule embeddings for existing global and company rules."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of rules to upsert before each commit.",
    )
    parser.add_argument(
        "--include-deleted",
        action="store_true",
        help="Also backfill soft-deleted rules.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_size = max(1, int(args.batch_size))

    with Session(engine) as session:
        stmt = select(Rule).order_by(Rule.created_at.asc(), Rule.id.asc())
        if not args.include_deleted:
            stmt = stmt.where(Rule.is_deleted.is_(False))

        rules = list(session.exec(stmt).all())
        total = len(rules)
        if total == 0:
            print("[backfill_rule_embeddings] No rules found.")
            return

        print(
            f"[backfill_rule_embeddings] total_rules={total} batch_size={batch_size} "
            f"include_deleted={bool(args.include_deleted)}"
        )

        processed = 0
        for start in range(0, total, batch_size):
            batch = rules[start : start + batch_size]
            inserted_or_updated = backfill_rule_embeddings(session=session, rules=batch)
            session.commit()
            processed += inserted_or_updated
            print(
                f"[backfill_rule_embeddings] batch={start // batch_size + 1} "
                f"processed={processed}/{total}"
            )

        print(f"[backfill_rule_embeddings] DONE processed={processed}")


if __name__ == "__main__":
    main()
