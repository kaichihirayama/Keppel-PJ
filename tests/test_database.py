"""Tests for DB connection/session setup (src/database/database.py)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from src.database.database import get_database_path, get_engine, init_db


def test_get_database_path_defaults_relative_to_project_root():
    path = get_database_path()
    assert path.is_absolute()
    assert path.name == "jreit.db"


def test_init_db_creates_all_tables(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = init_db(get_engine(db_path))
    table_names = set(inspect(engine).get_table_names())

    assert {
        "jreit_master",
        "properties",
        "property_metrics",
        "source_records",
    }.issubset(table_names)
    assert db_path.exists()
