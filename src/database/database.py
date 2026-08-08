"""Database engine/session management for the J-REIT underwriting PoC.

Uses SQLite for the PoC (section 3); DATABASE_PATH is read from the
environment (.env) so the location isn't hardcoded.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base

# Project root = two levels up from this file (src/database/database.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_DATABASE_PATH = "data/jreit.db"


def get_database_path() -> Path:
    raw_path = os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH)
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def get_engine(database_path: Path | None = None) -> Engine:
    db_path = database_path or get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(engine: Engine | None = None) -> Engine:
    """Create all tables if they don't already exist."""
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    engine = engine or get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


if __name__ == "__main__":
    eng = init_db()
    print(f"Initialized database at: {eng.url}")
