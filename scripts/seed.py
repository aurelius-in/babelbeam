"""Validate synthetic fixtures. Optionally mark the local database as seeded."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "terminology" / "mysterion_example.json"


def validate_fixture() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    terms = payload["terms"]
    if [term["canonical"] for term in terms] != ["mysterion", "mysterium", "sacramentum"]:
        raise SystemExit("Terminology fixture is missing the three protected terms.")
    if any(term["approved"] for term in terms):
        raise SystemExit("Seed fixtures must not mark terms approved.")
    print(f"Validated {FIXTURE.relative_to(ROOT)}")


def mark_database() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is unset. Skipped database seed. No users were created.")
        return
    if "localhost" not in database_url and "127.0.0.1" not in database_url:
        print("Refusing to seed a non-local DATABASE_URL. No users were created.")
        return
    from sqlalchemy import create_engine, text

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO app_metadata (key, value)
                VALUES ('phase0_seed', 'synthetic-fixtures-only')
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """
            )
        )
    print("Recorded phase0_seed=synthetic-fixtures-only. No users or grants were inserted.")


def main() -> None:
    validate_fixture()
    mark_database()


if __name__ == "__main__":
    main()
