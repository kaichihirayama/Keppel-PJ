"""SQLAlchemy ORM models for the J-REIT underwriting database.

Design notes (see project instructions section 5-6):
- Cap rates are never mixed into a single column: acquisition_cap_rate,
  appraisal_cap_rate, and noi_yield are tracked separately per period.
- occupancy_rate is stored as a normalized 0-100 percentage; the source
  document's own definition text is preserved in occupancy_rate_definition
  since REITs do not all define OCC the same way.
- rent_per_tsubo is normalized to JPY / tsubo / month; the pre-conversion
  value and unit are preserved for auditability.
- SourceRecord is a generic, field-level audit trail: one row per
  (table, record, field) documents where a value came from, so every
  extracted number can be traced back to its source document/page/table.
"""
from __future__ import annotations

import datetime as _dt

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# 1 tsubo in square meters (standard conversion factor, section 6).
TSUBO_IN_SQM = 3.305785


class Base(DeclarativeBase):
    pass


class JReitMaster(Base):
    """J-REIT master list (section 5.1)."""

    __tablename__ = "jreit_master"

    reit_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    reit_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sponsor: Mapped[str | None] = mapped_column(String(255))
    asset_type: Mapped[str | None] = mapped_column(String(64))
    edinet_code: Mapped[str | None] = mapped_column(String(16))
    website: Mapped[str | None] = mapped_column(String(255))

    properties: Mapped[list["Property"]] = relationship(
        back_populates="reit", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JReitMaster {self.reit_code} {self.reit_name}>"


class Property(Base):
    """Individual property held by a J-REIT (section 5.2)."""

    __tablename__ = "properties"

    property_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reit_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("jreit_master.reit_code"), nullable=False
    )
    property_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str | None] = mapped_column(String(64))

    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(64))
    ward: Mapped[str | None] = mapped_column(String(64))
    area: Mapped[str | None] = mapped_column(String(64))

    nearest_station: Mapped[str | None] = mapped_column(String(128))
    walking_minutes: Mapped[float | None] = mapped_column(Float)
    station_distance_m: Mapped[float | None] = mapped_column(Float)

    # Office grade is sometimes stated explicitly in the source document and
    # sometimes inferred; keep provenance and confidence separate from the
    # value itself (section 6).
    building_grade: Mapped[str | None] = mapped_column(String(32))
    building_grade_source: Mapped[str | None] = mapped_column(String(255))
    building_grade_confidence: Mapped[str | None] = mapped_column(String(16))

    year_built: Mapped[int | None] = mapped_column(Integer)
    total_floor_area: Mapped[float | None] = mapped_column(Float)
    leasable_area: Mapped[float | None] = mapped_column(Float)

    appraisal_value: Mapped[float | None] = mapped_column(Float)
    acquisition_price: Mapped[float | None] = mapped_column(Float)

    reit: Mapped["JReitMaster"] = relationship(back_populates="properties")
    metrics: Mapped[list["PropertyMetric"]] = relationship(
        back_populates="property_", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "acquisition_price IS NULL OR acquisition_price >= 0",
            name="ck_properties_acquisition_price_nonneg",
        ),
        CheckConstraint(
            "appraisal_value IS NULL OR appraisal_value >= 0",
            name="ck_properties_appraisal_value_nonneg",
        ),
    )

    def __repr__(self) -> str:
        return f"<Property {self.property_id} {self.property_name}>"


class PropertyMetric(Base):
    """Period-level financial/operating metrics for a property (section 5.3)."""

    __tablename__ = "property_metrics"

    metric_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.property_id"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(32), nullable=False)

    occupancy_rate: Mapped[float | None] = mapped_column(Float)
    # Source document's own OCC definition, when it differs from the
    # standardized definition used across this database (section 6).
    occupancy_rate_definition: Mapped[str | None] = mapped_column(String(255))

    rent_per_tsubo: Mapped[float | None] = mapped_column(Float)
    rent_per_tsubo_raw_value: Mapped[float | None] = mapped_column(Float)
    rent_per_tsubo_raw_unit: Mapped[str | None] = mapped_column(String(64))

    noi: Mapped[float | None] = mapped_column(Float)

    # Cap rate variants are kept in separate columns; never conflated.
    acquisition_cap_rate: Mapped[float | None] = mapped_column(Float)
    appraisal_cap_rate: Mapped[float | None] = mapped_column(Float)
    noi_yield: Mapped[float | None] = mapped_column(Float)

    property_: Mapped["Property"] = relationship(back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("property_id", "period", name="uq_property_metrics_property_period"),
        CheckConstraint(
            "occupancy_rate IS NULL OR (occupancy_rate >= 0 AND occupancy_rate <= 100)",
            name="ck_property_metrics_occupancy_rate_range",
        ),
        CheckConstraint(
            "rent_per_tsubo IS NULL OR rent_per_tsubo >= 0",
            name="ck_property_metrics_rent_per_tsubo_nonneg",
        ),
    )

    def __repr__(self) -> str:
        return f"<PropertyMetric property={self.property_id} period={self.period}>"


class SourceRecord(Base):
    """Field-level audit trail (section 5.4).

    One row per extracted value: which table/record/field it populates,
    where it came from, how it was extracted, and how confident/validated
    that extraction is. This lets every number in the database be traced
    back to a source document, page, and table.
    """

    __tablename__ = "source_records"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)

    source_document: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(512))
    source_page: Mapped[str | None] = mapped_column(String(32))
    source_table: Mapped[str | None] = mapped_column(String(128))
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[str | None] = mapped_column(String(16))

    extracted_at: Mapped[_dt.datetime] = mapped_column(
        DateTime, default=lambda: _dt.datetime.now(_dt.timezone.utc), nullable=False
    )
    # approved / review / rejected (section 9).
    validation_status: Mapped[str] = mapped_column(String(16), default="review", nullable=False)

    __table_args__ = (
        CheckConstraint(
            "validation_status IN ('approved', 'review', 'rejected')",
            name="ck_source_records_validation_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<SourceRecord {self.table_name}.{self.field_name} record={self.record_id}>"
