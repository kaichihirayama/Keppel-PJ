"""Tests for basic ORM data model behavior (src/database/models.py)."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import JReitMaster, Property, PropertyMetric, SourceRecord


def test_insert_and_query_jreit_master(db_session):
    db_session.add(
        JReitMaster(
            reit_code="8951",
            reit_name="日本ビルファンド投資法人",
            sponsor="三井不動産",
            asset_type="オフィス",
        )
    )
    db_session.commit()

    fetched = db_session.get(JReitMaster, "8951")
    assert fetched is not None
    assert fetched.reit_name == "日本ビルファンド投資法人"


def test_property_links_to_reit_via_relationship(db_session):
    reit = JReitMaster(reit_code="8951", reit_name="日本ビルファンド投資法人")
    db_session.add(reit)
    db_session.flush()

    prop = Property(
        reit_code="8951",
        property_name="Sample Office Bldg",
        asset_type="オフィス",
        building_grade="A",
        building_grade_source="有価証券報告書 p.10",
        building_grade_confidence="high",
    )
    db_session.add(prop)
    db_session.commit()

    assert prop in reit.properties
    assert prop.reit.reit_code == "8951"


def test_occupancy_rate_out_of_range_is_rejected(db_session):
    reit = JReitMaster(reit_code="8951", reit_name="Test REIT")
    db_session.add(reit)
    db_session.flush()

    prop = Property(reit_code="8951", property_name="Sample Bldg")
    db_session.add(prop)
    db_session.flush()

    db_session.add(
        PropertyMetric(property_id=prop.property_id, period="2024-09", occupancy_rate=150.0)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_cap_rate_columns_are_kept_separate(db_session):
    reit = JReitMaster(reit_code="8951", reit_name="Test REIT")
    db_session.add(reit)
    db_session.flush()

    prop = Property(reit_code="8951", property_name="Sample Bldg")
    db_session.add(prop)
    db_session.flush()

    metric = PropertyMetric(
        property_id=prop.property_id,
        period="2024-09",
        acquisition_cap_rate=4.2,
        appraisal_cap_rate=4.0,
        noi_yield=4.5,
    )
    db_session.add(metric)
    db_session.commit()

    fetched = db_session.get(PropertyMetric, metric.metric_id)
    assert fetched.acquisition_cap_rate == 4.2
    assert fetched.appraisal_cap_rate == 4.0
    assert fetched.noi_yield == 4.5


def test_source_record_tracks_field_level_provenance(db_session):
    record = SourceRecord(
        table_name="property_metrics",
        record_id="1",
        field_name="occupancy_rate",
        source_document="有価証券報告書",
        source_page="45",
        source_table="物件概要表",
        extraction_method="pdf_table",
        confidence="high",
        validation_status="review",
    )
    db_session.add(record)
    db_session.commit()

    fetched = db_session.get(SourceRecord, record.source_id)
    assert fetched.validation_status == "review"
    assert fetched.field_name == "occupancy_rate"


def test_invalid_validation_status_is_rejected(db_session):
    record = SourceRecord(
        table_name="property_metrics",
        record_id="1",
        field_name="occupancy_rate",
        validation_status="not_a_real_status",
    )
    db_session.add(record)
    with pytest.raises(IntegrityError):
        db_session.commit()
