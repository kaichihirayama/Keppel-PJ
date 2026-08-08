"""Seed jreit_master from config/poc_targets.yaml.

Idempotent: existing rows (matched by reit_code) are left untouched.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.config import load_poc_targets
from src.database.database import get_session_factory, init_db
from src.database.models import JReitMaster


def seed_jreit_master(session: Session) -> int:
    targets = load_poc_targets()
    inserted = 0
    for target in targets:
        exists = session.get(JReitMaster, target["reit_code"])
        if exists:
            continue
        session.add(
            JReitMaster(
                reit_code=target["reit_code"],
                reit_name=target["reit_name"],
                sponsor=target.get("sponsor"),
                asset_type=target.get("asset_type"),
                edinet_code=target.get("edinet_code"),
                website=target.get("website"),
            )
        )
        inserted += 1
    session.commit()
    return inserted


if __name__ == "__main__":
    engine = init_db()
    SessionLocal = get_session_factory(engine)
    with SessionLocal() as db_session:
        count = seed_jreit_master(db_session)
        print(f"Inserted {count} new JReitMaster rows.")
