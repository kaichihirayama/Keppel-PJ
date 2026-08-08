"""Shared pytest fixtures: an in-memory SQLite DB per test."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine) -> Session:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
