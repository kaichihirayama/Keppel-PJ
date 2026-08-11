"""Combine period-level metrics into a single trailing-12-month figure.

J-REITs report on different cycles: most report every 6 months (半期), a
few report a full fiscal year (通期) at once. Before comparing properties
across REITs, each property's most recent metrics need to represent the
same length of time. The rule (per project instructions):

- If the most recent record already covers a full year, use it directly.
- If the two most recent records are consecutive 6-month periods, combine
  them into one annual figure:
    - flow metrics (money earned/spent over the period, e.g. NOI) are
      SUMMED across the two halves.
    - rate metrics (a ratio or unit price at/around a point in time, e.g.
      occupancy_rate, rent_per_tsubo, the cap rate variants) are AVERAGED.
- If a metric is missing (None) on either half, the combined value is
  None rather than guessed — see AnnualizedMetric.missing_fields.
- If there isn't enough data to do either (no annual record and no pair
  of consecutive semi-annual records), no result is produced.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.database.models import PropertyMetric

# Metrics that represent money earned/spent over the period: summed when
# combining two half-year periods into one annual figure.
FLOW_FIELDS = ("noi",)

# Metrics that represent a ratio or unit price: averaged when combining.
RATE_FIELDS = (
    "occupancy_rate",
    "rent_per_tsubo",
    "acquisition_cap_rate",
    "appraisal_cap_rate",
    "noi_yield",
)

CONSECUTIVE_SEMI_ANNUAL_MONTH_GAP = 6


@dataclass
class AnnualizedMetric:
    property_id: int
    method: str  # "annual_direct" or "semi_annual_combined"
    source_periods: list[str]

    occupancy_rate: float | None = None
    rent_per_tsubo: float | None = None
    noi: float | None = None
    acquisition_cap_rate: float | None = None
    appraisal_cap_rate: float | None = None
    noi_yield: float | None = None

    # Fields that could not be computed because at least one source period
    # was missing that value (never silently guessed/zero-filled).
    missing_fields: list[str] = field(default_factory=list)


def _months_between(a, b) -> int:
    return abs((a.year - b.year) * 12 + (a.month - b.month))


def annualize_metrics(metrics: list[PropertyMetric]) -> AnnualizedMetric | None:
    """Return a trailing-12-month AnnualizedMetric for one property.

    ``metrics`` should be all PropertyMetric rows for a single property, in
    any order; only period_type/period_end_date and the metric columns are
    used, so plain PropertyMetric instances (persisted or not) both work.
    Returns None if there isn't enough data to produce a full-year figure.
    """
    dated = [m for m in metrics if m.period_end_date is not None]
    if not dated:
        return None
    dated.sort(key=lambda m: m.period_end_date, reverse=True)

    latest = dated[0]
    if latest.period_type == "annual":
        return AnnualizedMetric(
            property_id=latest.property_id,
            method="annual_direct",
            source_periods=[latest.period],
            occupancy_rate=latest.occupancy_rate,
            rent_per_tsubo=latest.rent_per_tsubo,
            noi=latest.noi,
            acquisition_cap_rate=latest.acquisition_cap_rate,
            appraisal_cap_rate=latest.appraisal_cap_rate,
            noi_yield=latest.noi_yield,
        )

    semi_annual = [m for m in dated if m.period_type == "semi_annual"]
    if len(semi_annual) < 2:
        return None

    first, second = semi_annual[0], semi_annual[1]
    if _months_between(first.period_end_date, second.period_end_date) != (
        CONSECUTIVE_SEMI_ANNUAL_MONTH_GAP
    ):
        return None

    result = AnnualizedMetric(
        property_id=first.property_id,
        method="semi_annual_combined",
        source_periods=[first.period, second.period],
    )

    for attr in FLOW_FIELDS:
        v1, v2 = getattr(first, attr), getattr(second, attr)
        if v1 is None or v2 is None:
            result.missing_fields.append(attr)
        else:
            setattr(result, attr, v1 + v2)

    for attr in RATE_FIELDS:
        v1, v2 = getattr(first, attr), getattr(second, attr)
        if v1 is None or v2 is None:
            result.missing_fields.append(attr)
        else:
            setattr(result, attr, (v1 + v2) / 2)

    return result
