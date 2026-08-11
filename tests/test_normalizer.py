"""Tests for trailing-12-month annualization (src/extraction/normalizer.py)."""
from __future__ import annotations

import datetime as dt

import pytest

from src.extraction.normalizer import annualize_metrics


def _metric(period, period_type, period_end_date, **kwargs):
    from src.database.models import PropertyMetric

    return PropertyMetric(
        property_id=1,
        period=period,
        period_type=period_type,
        period_end_date=period_end_date,
        **kwargs,
    )


def test_annual_period_is_used_directly():
    metrics = [
        _metric(
            "2024年3月期",
            "annual",
            dt.date(2024, 3, 31),
            occupancy_rate=95.0,
            noi=1000.0,
            acquisition_cap_rate=4.5,
        )
    ]
    result = annualize_metrics(metrics)

    assert result.method == "annual_direct"
    assert result.noi == 1000.0
    assert result.occupancy_rate == 95.0
    assert result.missing_fields == []


def test_two_consecutive_semi_annual_periods_are_combined():
    metrics = [
        _metric(
            "2024年3月期",
            "semi_annual",
            dt.date(2024, 3, 31),
            occupancy_rate=94.0,
            rent_per_tsubo=20000.0,
            noi=500.0,
            acquisition_cap_rate=4.4,
            appraisal_cap_rate=4.2,
            noi_yield=4.3,
        ),
        _metric(
            "2023年9月期",
            "semi_annual",
            dt.date(2023, 9, 30),
            occupancy_rate=96.0,
            rent_per_tsubo=22000.0,
            noi=480.0,
            acquisition_cap_rate=4.6,
            appraisal_cap_rate=4.4,
            noi_yield=4.5,
        ),
    ]
    result = annualize_metrics(metrics)

    assert result.method == "semi_annual_combined"
    # Flow metric: summed.
    assert result.noi == 980.0
    # Rate metrics: averaged.
    assert result.occupancy_rate == 95.0
    assert result.rent_per_tsubo == 21000.0
    assert result.acquisition_cap_rate == pytest.approx(4.5)
    assert result.appraisal_cap_rate == pytest.approx(4.3)
    assert result.noi_yield == pytest.approx(4.4)
    assert result.missing_fields == []
    assert result.source_periods == ["2024年3月期", "2023年9月期"]


def test_missing_value_on_one_half_is_not_guessed():
    metrics = [
        _metric("2024年3月期", "semi_annual", dt.date(2024, 3, 31), noi=500.0, occupancy_rate=94.0),
        _metric("2023年9月期", "semi_annual", dt.date(2023, 9, 30), noi=None, occupancy_rate=96.0),
    ]
    result = annualize_metrics(metrics)

    assert result.noi is None
    assert "noi" in result.missing_fields
    assert result.occupancy_rate == 95.0
    assert "occupancy_rate" not in result.missing_fields


def test_non_consecutive_semi_annual_periods_are_not_combined():
    metrics = [
        _metric("2024年9月期", "semi_annual", dt.date(2024, 9, 30), noi=500.0),
        _metric("2023年9月期", "semi_annual", dt.date(2023, 9, 30), noi=480.0),
    ]
    assert annualize_metrics(metrics) is None


def test_single_semi_annual_period_is_insufficient():
    metrics = [_metric("2024年3月期", "semi_annual", dt.date(2024, 3, 31), noi=500.0)]
    assert annualize_metrics(metrics) is None


def test_no_metrics_returns_none():
    assert annualize_metrics([]) is None


def test_metrics_without_period_end_date_are_ignored():
    metrics = [_metric("unknown period", None, None, noi=500.0)]
    assert annualize_metrics(metrics) is None
