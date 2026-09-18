"""Domain objects returned by the Customer API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any


class Aggregation(str, Enum):
    """Time aggregation values accepted by GetTimeSeries."""

    ACTUAL = "Actual"
    QUARTER = "Quarter"
    HOUR = "Hour"
    DAY = "Day"
    MONTH = "Month"
    YEAR = "Year"


@dataclass
class MeteringPoint:
    """One electricity address / metering point linked to the API key."""

    metering_point_id: str
    name: str | None = None
    type_of_mp: str | None = None
    street_name: str | None = None
    building_number: str | None = None
    postcode: str | None = None
    city_name: str | None = None
    has_relation: bool = False
    is_moved_out: bool = False
    meter_number: str | None = None
    consumer_start_date: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MeteringPoint:
        return cls(
            metering_point_id=data.get("meteringPointId") or "",
            name=_consumer_name(data),
            type_of_mp=data.get("typeOfMP"),
            street_name=data.get("streetName"),
            building_number=data.get("buildingNumber"),
            postcode=data.get("postcode"),
            city_name=data.get("cityName"),
            has_relation=bool(data.get("hasRelation")),
            is_moved_out=bool(data.get("isMovedOut")),
            meter_number=data.get("meterNumber"),
            consumer_start_date=data.get("consumerStartDate"),
            raw=data,
        )

    @property
    def address(self) -> str:
        parts = [
            self.street_name,
            self.building_number,
            self.postcode,
            self.city_name,
        ]
        return " ".join(part for part in parts if part)

    @property
    def is_active(self) -> bool:
        return not self.is_moved_out

    @property
    def status(self) -> str:
        return "moved_out" if self.is_moved_out else "active"

    def matches(self, query: str) -> bool:
        """True if query matches id, consumer name, or street address."""
        needle = query.strip().casefold()
        if not needle:
            return False
        haystacks = [
            self.metering_point_id,
            self.name or "",
            self.address,
            self.street_name or "",
        ]
        return any(needle in item.casefold() for item in haystacks if item)


@dataclass
class TimeSeriesPoint:
    """One measured or aggregated quantity from a time series."""

    metering_point_id: str
    start: datetime | None
    quantity: float | None
    unit: str | None
    quality: str | None
    resolution: str | None
    aggregation: Aggregation
    position: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class TimeSeries:
    """Parsed time series for one metering point and aggregation."""

    metering_point_id: str
    aggregation: Aggregation
    unit: str | None
    business_type: str | None
    points: list[TimeSeriesPoint] = field(default_factory=list)
    success: bool = True
    error_code: int | None = None
    error_text: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], aggregation: Aggregation) -> TimeSeries:
        document = data.get("MyEnergyData_MarketDocument") or {}
        series_list = document.get("TimeSeries") or []
        first = series_list[0] if series_list else {}
        metering_point_id = (
            data.get("id")
            or first.get("mRID")
            or _market_evaluation_point_id(first)
            or ""
        )
        unit = first.get("measurement_Unit.name")
        points: list[TimeSeriesPoint] = []
        for series in series_list:
            series_id = series.get("mRID") or metering_point_id
            series_unit = series.get("measurement_Unit.name") or unit
            for period in series.get("Period") or []:
                resolution = period.get("resolution")
                interval = period.get("timeInterval") or {}
                period_start = _parse_datetime(interval.get("start"))
                step = _resolution_step(resolution)
                for point in period.get("Point") or []:
                    position = _as_int(point.get("position"))
                    start = period_start
                    if start is not None and step is not None and position:
                        start = start + step * (position - 1)
                    points.append(
                        TimeSeriesPoint(
                            metering_point_id=series_id,
                            start=start,
                            quantity=_as_float(point.get("out_Quantity.quantity")),
                            unit=series_unit,
                            quality=point.get("out_Quantity.quality"),
                            resolution=resolution,
                            aggregation=aggregation,
                            position=position,
                            raw=point,
                        )
                    )
        return cls(
            metering_point_id=metering_point_id,
            aggregation=aggregation,
            unit=unit,
            business_type=first.get("businessType"),
            points=points,
            success=bool(data.get("success", True)),
            error_code=data.get("errorCode"),
            error_text=data.get("errorText"),
            raw=data,
        )

    def total(self) -> float:
        return sum(point.quantity or 0.0 for point in self.points)


def _consumer_name(data: dict[str, Any]) -> str | None:
    first = (data.get("firstConsumerPartyName") or "").strip()
    second = (data.get("secondConsumerPartyName") or "").strip()
    if first and second:
        return f"{first} / {second}"
    return first or second or None


def _market_evaluation_point_id(series: dict[str, Any]) -> str:
    point = series.get("MarketEvaluationPoint") or {}
    mrid = point.get("mRID") or {}
    if isinstance(mrid, dict):
        return mrid.get("name") or ""
    return str(mrid or "")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolution_step(resolution: str | None) -> timedelta | None:
    mapping = {
        "PT15M": timedelta(minutes=15),
        "PT1H": timedelta(hours=1),
        "PT1D": timedelta(days=1),
        "P1D": timedelta(days=1),
    }
    return mapping.get(resolution or "")


def as_date_str(value: date | datetime | str) -> str:
    """Normalize a date argument to YYYY-MM-DD."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
