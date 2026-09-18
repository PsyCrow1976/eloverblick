"""Day-ahead hourly electricity prices from Energi Data Service."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from web import db

TIMEZONE = ZoneInfo("Europe/Copenhagen")
DATASET_URL = "https://api.energidataservice.dk/dataset/DayAheadPrices"
DEFAULT_AREA = "DK2"


def price_area() -> str:
    return os.environ.get("PRICE_AREA", DEFAULT_AREA).strip().upper() or DEFAULT_AREA


def pull_today_and_tomorrow(area: str | None = None) -> str:
    """Fetch today and tomorrow, average 15-minute prices to hours, upsert."""
    area = (area or price_area()).upper()
    today = datetime.now(TIMEZONE).date()
    tomorrow = today + timedelta(days=1)
    records = _fetch_records(area, today, tomorrow + timedelta(days=1))
    hours = _to_hourly(area, records)
    if not hours:
        raise RuntimeError(
            f"No DayAheadPrices returned for {area} covering {today}–{tomorrow}."
        )
    stored = db.replace_hour_prices(hours)
    by_day: dict[date, int] = defaultdict(int)
    for row in hours:
        by_day[row["local_date"]] += 1
    today_n = by_day.get(today, 0)
    tomorrow_n = by_day.get(tomorrow, 0)
    extra = []
    if today_n == 0:
        extra.append("today missing")
    if tomorrow_n == 0:
        extra.append("tomorrow not published yet")
    note = f" ({', '.join(extra)})" if extra else ""
    return (
        f"Stored {stored} hourly prices for {area}: "
        f"today {today.isoformat()} {today_n} hours, "
        f"tomorrow {tomorrow.isoformat()} {tomorrow_n} hours{note}."
    )


def _fetch_records(area: str, start: date, end: date) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "filter": json.dumps({"PriceArea": [area]}),
            "sort": "TimeUTC ASC",
            "limit": "500",
        }
    )
    url = f"{DATASET_URL}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"DayAheadPrices HTTP {exc.code} {exc.reason}: {body[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DayAheadPrices request failed: {exc.reason}") from exc
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise RuntimeError("DayAheadPrices response had no records list.")
    return [row for row in records if isinstance(row, dict)]


def _to_hourly(area: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        utc = _parse_utc(row.get("TimeUTC"))
        if utc is None:
            continue
        hour_utc = utc.replace(minute=0, second=0, microsecond=0)
        groups[hour_utc].append(row)
    hours = []
    for hour_utc, items in sorted(groups.items()):
        local = hour_utc.astimezone(TIMEZONE)
        dkk = _mean([item.get("DayAheadPriceDKK") for item in items])
        eur = _mean([item.get("DayAheadPriceEUR") for item in items])
        hours.append(
            {
                "price_area": area,
                "period_start": hour_utc,
                "local_date": local.date(),
                "local_hour": local.hour,
                "price_dkk_mwh": dkk,
                "price_eur_mwh": eur,
            }
        )
    return hours


def _parse_utc(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mean(values: list[Any]) -> Decimal | None:
    numbers: list[Decimal] = []
    for value in values:
        if value is None or value == "":
            continue
        try:
            numbers.append(Decimal(str(value)))
        except Exception:
            continue
    if not numbers:
        return None
    return sum(numbers, Decimal("0")) / len(numbers)
