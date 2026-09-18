"""Pull Customer API usage into PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from script import CustomerApi
from script.exceptions import ApiError, ElOverblikError
from script.models import TimeSeriesPoint, as_date_str
from web import db

TIMEZONE = ZoneInfo("Europe/Copenhagen")

_api: CustomerApi | None = None


@dataclass
class PullResult:
    status: str
    message: str
    location: str


def customer_api() -> CustomerApi:
    global _api
    if _api is None:
        api = CustomerApi.from_env(timezone=TIMEZONE)
        point = api.select_address()
        db.upsert_metering_point(point)
        _api = api
    return _api


def meter_id() -> str | None:
    api = _api
    if api is not None and api.selected_address is not None:
        return api.selected_address.metering_point_id
    stored = db.any_meter_id()
    if stored:
        return stored
    try:
        return customer_api().selected_address.metering_point_id
    except ElOverblikError:
        return None


def pull_day(day: date, *, replace: bool = False) -> PullResult:
    location = _day_path(day)
    api = customer_api()
    meter = api.selected_address.metering_point_id
    existing = db.get_day(meter, day)
    if existing is not None and not replace:
        return PullResult("exists", "already stored", f"{location}/confirm")

    hours_series = api.hours_for_day(day)
    if not hours_series.success:
        raise ApiError(
            hours_series.error_text or f"No hourly data for {as_date_str(day)}.",
            error_code=hours_series.error_code,
            body=hours_series.raw,
        )
    day_total = api.usage_for_date(day)
    hour_rows = [_hour_payload(point, day) for point in hours_series.points]
    hour_rows = [row for row in hour_rows if row is not None]
    if not hour_rows:
        raise ApiError(f"No hourly readings returned for {as_date_str(day)}.")

    db.upsert_metering_point(api.selected_address)
    db.replace_day(
        meter,
        day,
        day_total,
        hours_series.unit,
        hour_rows,
    )
    return PullResult(
        "ok",
        f"Stored {as_date_str(day)}: {day_total} kWh and {len(hour_rows)} hours.",
        location,
    )


def pull_month(year: int, month: int, *, replace: bool = False) -> PullResult:
    location = f"/{year}/{month:02d}"
    api = customer_api()
    meter = api.selected_address.metering_point_id
    if db.month_has_row(meter, year, month) and not replace:
        return PullResult("exists", "already stored", f"{location}/confirm")

    series = api.days_for_month(year, month)
    if not series.success:
        raise ApiError(
            series.error_text or f"No daily data for {year}-{month:02d}.",
            error_code=series.error_code,
            body=series.raw,
        )
    days = []
    for point in series.points:
        local_day = _local_date(point.start)
        if local_day is None:
            continue
        days.append(
            {
                "day": local_day,
                "usage_kwh": point.quantity or 0.0,
                "unit": point.unit or series.unit,
            }
        )
    if not days:
        raise ApiError(f"No daily readings returned for {year}-{month:02d}.")

    db.upsert_metering_point(api.selected_address)
    db.replace_month(meter, year, month, series.total(), series.unit, days)
    return PullResult(
        "ok",
        f"Stored {year}-{month:02d}: {series.total()} kWh across {len(days)} days.",
        location,
    )


def pull_year(year: int, *, replace: bool = False) -> PullResult:
    location = f"/{year}"
    api = customer_api()
    meter = api.selected_address.metering_point_id
    if db.year_has_row(meter, year) and not replace:
        return PullResult("exists", "already stored", f"{location}/confirm")

    series = api.months_for_year(year)
    if not series.success:
        raise ApiError(
            series.error_text or f"No monthly data for {year}.",
            error_code=series.error_code,
            body=series.raw,
        )
    months = []
    for point in series.points:
        local_day = _local_date(point.start)
        if local_day is None:
            continue
        months.append(
            {
                "month": local_day.month,
                "usage_kwh": point.quantity or 0.0,
                "unit": point.unit or series.unit,
            }
        )
    if not months:
        raise ApiError(f"No monthly readings returned for {year}.")

    db.upsert_metering_point(api.selected_address)
    db.replace_year(meter, year, series.total(), series.unit, months)
    return PullResult(
        "ok",
        f"Stored {year}: {series.total()} kWh across {len(months)} months.",
        location,
    )


def _hour_payload(point: TimeSeriesPoint, day: date) -> dict | None:
    if point.start is None or point.quantity is None:
        return None
    start = point.start
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    local = start.astimezone(TIMEZONE)
    return {
        "period_start": start.astimezone(timezone.utc),
        "local_date": day,
        "local_hour": local.hour,
        "usage_kwh": point.quantity,
        "unit": point.unit,
        "quality": point.quality,
    }


def _local_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TIMEZONE).date()


def _day_path(day: date) -> str:
    return f"/{day.year}/{day.month:02d}/{day.day:02d}"
