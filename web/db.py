"""PostgreSQL access for stored ElOverblik usage."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from script.models import MeteringPoint

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS eloverblick;

CREATE TABLE IF NOT EXISTS eloverblick.metering_points (
    metering_point_id text PRIMARY KEY,
    name text,
    address text,
    status text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eloverblick.hours (
    metering_point_id text NOT NULL
        REFERENCES eloverblick.metering_points (metering_point_id),
    period_start timestamptz NOT NULL,
    local_date date NOT NULL,
    local_hour smallint NOT NULL,
    usage_kwh numeric(14, 6) NOT NULL,
    unit text,
    quality text,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metering_point_id, period_start)
);

CREATE INDEX IF NOT EXISTS hours_local_date_idx
    ON eloverblick.hours (metering_point_id, local_date);

CREATE TABLE IF NOT EXISTS eloverblick.days (
    metering_point_id text NOT NULL
        REFERENCES eloverblick.metering_points (metering_point_id),
    day date NOT NULL,
    usage_kwh numeric(14, 6) NOT NULL,
    unit text,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metering_point_id, day)
);

CREATE TABLE IF NOT EXISTS eloverblick.months (
    metering_point_id text NOT NULL
        REFERENCES eloverblick.metering_points (metering_point_id),
    year integer NOT NULL,
    month integer NOT NULL CHECK (month BETWEEN 1 AND 12),
    usage_kwh numeric(14, 6) NOT NULL,
    unit text,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metering_point_id, year, month)
);

CREATE TABLE IF NOT EXISTS eloverblick.years (
    metering_point_id text NOT NULL
        REFERENCES eloverblick.metering_points (metering_point_id),
    year integer NOT NULL,
    usage_kwh numeric(14, 6) NOT NULL,
    unit text,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metering_point_id, year)
);

CREATE TABLE IF NOT EXISTS eloverblick.hour_prices (
    price_area text NOT NULL,
    period_start timestamptz NOT NULL,
    local_date date NOT NULL,
    local_hour smallint NOT NULL,
    price_dkk_mwh numeric(14, 6),
    price_eur_mwh numeric(14, 6),
    scraped_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (price_area, period_start)
);

CREATE INDEX IF NOT EXISTS hour_prices_local_date_idx
    ON eloverblick.hour_prices (price_area, local_date);

CREATE TABLE IF NOT EXISTS eloverblick.job_logs (
    id bigserial PRIMARY KEY,
    logged_at timestamptz NOT NULL DEFAULT now(),
    instance text NOT NULL,
    job_name text NOT NULL,
    success boolean NOT NULL,
    output text NOT NULL
);

CREATE INDEX IF NOT EXISTS job_logs_logged_at_idx
    ON eloverblick.job_logs (logged_at DESC);

CREATE TABLE IF NOT EXISTS eloverblick.job_state (
    job_name text PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT true,
    interval_hours integer NOT NULL DEFAULT 6,
    last_run_at timestamptz,
    last_success boolean,
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""


@dataclass
class DayRow:
    metering_point_id: str
    day: date
    usage_kwh: Decimal
    unit: str | None
    scraped_at: datetime
    hour_count: int = 0


@dataclass
class HourRow:
    metering_point_id: str
    period_start: datetime
    local_date: date
    local_hour: int
    usage_kwh: Decimal
    unit: str | None
    quality: str | None
    scraped_at: datetime


@dataclass
class MonthRow:
    metering_point_id: str
    year: int
    month: int
    usage_kwh: Decimal
    unit: str | None
    scraped_at: datetime
    day_count: int = 0


@dataclass
class YearRow:
    metering_point_id: str
    year: int
    usage_kwh: Decimal
    unit: str | None
    scraped_at: datetime
    month_count: int = 0


@dataclass
class MeterRow:
    metering_point_id: str
    name: str | None
    address: str | None
    status: str | None


@dataclass
class HourPriceRow:
    price_area: str
    period_start: datetime
    local_date: date
    local_hour: int
    price_dkk_mwh: Decimal | None
    price_eur_mwh: Decimal | None
    scraped_at: datetime


@dataclass
class JobLogRow:
    id: int
    logged_at: datetime
    instance: str
    job_name: str
    success: bool
    output: str


@dataclass
class JobStateRow:
    job_name: str
    enabled: bool
    interval_hours: int
    last_run_at: datetime | None
    last_success: bool | None
    updated_at: datetime


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        if default is not None:
            return default
        raise RuntimeError(f"{name} must be set.")
    return value


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=_env("POSTGRES_HOST"),
        port=int(_env("POSTGRES_PORT", "5432")),
        user=_env("POSTGRES_USER"),
        password=_env("POSTGRES_PASSWORD"),
        dbname=_env("POSTGRES_DB", "home"),
        row_factory=dict_row,
        connect_timeout=10,
    )


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()


def upsert_metering_point(point: MeteringPoint) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO eloverblick.metering_points (
                metering_point_id, name, address, status, updated_at
            )
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (metering_point_id) DO UPDATE SET
                name = EXCLUDED.name,
                address = EXCLUDED.address,
                status = EXCLUDED.status,
                updated_at = now()
            """,
            (point.metering_point_id, point.name, point.address, point.status),
        )
        conn.commit()


def get_meter(metering_point_id: str) -> MeterRow | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT metering_point_id, name, address, status
            FROM eloverblick.metering_points
            WHERE metering_point_id = %s
            """,
            (metering_point_id,),
        ).fetchone()
    return MeterRow(**row) if row else None


def any_meter_id() -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT metering_point_id
            FROM eloverblick.metering_points
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
    return row["metering_point_id"] if row else None


def list_years(metering_point_id: str) -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT year FROM (
                SELECT year FROM eloverblick.years
                WHERE metering_point_id = %s
                UNION
                SELECT year FROM eloverblick.months
                WHERE metering_point_id = %s
                UNION
                SELECT EXTRACT(YEAR FROM day)::int
                FROM eloverblick.days
                WHERE metering_point_id = %s
                UNION
                SELECT EXTRACT(YEAR FROM local_date)::int
                FROM eloverblick.hours
                WHERE metering_point_id = %s
            ) years
            ORDER BY year DESC
            """,
            (metering_point_id, metering_point_id, metering_point_id, metering_point_id),
        ).fetchall()
    return [int(row["year"]) for row in rows]


def get_year(metering_point_id: str, year: int) -> YearRow | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT y.metering_point_id, y.year, y.usage_kwh, y.unit, y.scraped_at,
                   (
                       SELECT COUNT(*) FROM eloverblick.months m
                       WHERE m.metering_point_id = y.metering_point_id
                         AND m.year = y.year
                   ) AS month_count
            FROM eloverblick.years y
            WHERE y.metering_point_id = %s AND y.year = %s
            """,
            (metering_point_id, year),
        ).fetchone()
    return _year_row(row) if row else None


def list_months(metering_point_id: str, year: int) -> list[MonthRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT m.metering_point_id, m.year, m.month, m.usage_kwh, m.unit,
                   m.scraped_at,
                   (
                       SELECT COUNT(*) FROM eloverblick.days d
                       WHERE d.metering_point_id = m.metering_point_id
                         AND EXTRACT(YEAR FROM d.day) = m.year
                         AND EXTRACT(MONTH FROM d.day) = m.month
                   ) AS day_count
            FROM eloverblick.months m
            WHERE m.metering_point_id = %s AND m.year = %s
            ORDER BY m.month
            """,
            (metering_point_id, year),
        ).fetchall()
    stored = [_month_row(row) for row in rows]
    have = {item.month for item in stored}
    with connect() as conn:
        extra = conn.execute(
            """
            SELECT EXTRACT(MONTH FROM day)::int AS month,
                   COUNT(*) AS day_count,
                   SUM(usage_kwh) AS usage_kwh,
                   MAX(scraped_at) AS scraped_at,
                   MIN(unit) AS unit
            FROM eloverblick.days
            WHERE metering_point_id = %s
              AND EXTRACT(YEAR FROM day) = %s
            GROUP BY 1
            ORDER BY 1
            """,
            (metering_point_id, year),
        ).fetchall()
    for row in extra:
        month = int(row["month"])
        if month in have:
            continue
        stored.append(
            MonthRow(
                metering_point_id=metering_point_id,
                year=year,
                month=month,
                usage_kwh=row["usage_kwh"],
                unit=row["unit"],
                scraped_at=row["scraped_at"],
                day_count=int(row["day_count"]),
            )
        )
        have.add(month)
    stored.sort(key=lambda item: item.month)
    return stored


def get_month(metering_point_id: str, year: int, month: int) -> MonthRow | None:
    months = [item for item in list_months(metering_point_id, year) if item.month == month]
    return months[0] if months else None


def month_has_row(metering_point_id: str, year: int, month: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM eloverblick.months
            WHERE metering_point_id = %s AND year = %s AND month = %s
            """,
            (metering_point_id, year, month),
        ).fetchone()
    return row is not None


def year_has_row(metering_point_id: str, year: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM eloverblick.years
            WHERE metering_point_id = %s AND year = %s
            """,
            (metering_point_id, year),
        ).fetchone()
    return row is not None


def list_days(metering_point_id: str, year: int, month: int) -> list[DayRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.metering_point_id, d.day, d.usage_kwh, d.unit, d.scraped_at,
                   (
                       SELECT COUNT(*) FROM eloverblick.hours h
                       WHERE h.metering_point_id = d.metering_point_id
                         AND h.local_date = d.day
                   ) AS hour_count
            FROM eloverblick.days d
            WHERE d.metering_point_id = %s
              AND EXTRACT(YEAR FROM d.day) = %s
              AND EXTRACT(MONTH FROM d.day) = %s
            ORDER BY d.day
            """,
            (metering_point_id, year, month),
        ).fetchall()
    return [_day_row(row) for row in rows]


def get_day(metering_point_id: str, day: date) -> DayRow | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT d.metering_point_id, d.day, d.usage_kwh, d.unit, d.scraped_at,
                   (
                       SELECT COUNT(*) FROM eloverblick.hours h
                       WHERE h.metering_point_id = d.metering_point_id
                         AND h.local_date = d.day
                   ) AS hour_count
            FROM eloverblick.days d
            WHERE d.metering_point_id = %s AND d.day = %s
            """,
            (metering_point_id, day),
        ).fetchone()
    return _day_row(row) if row else None


def list_hours(metering_point_id: str, day: date) -> list[HourRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT metering_point_id, period_start, local_date, local_hour,
                   usage_kwh, unit, quality, scraped_at
            FROM eloverblick.hours
            WHERE metering_point_id = %s AND local_date = %s
            ORDER BY period_start
            """,
            (metering_point_id, day),
        ).fetchall()
    return [_hour_row(row) for row in rows]


def replace_day(
    metering_point_id: str,
    day: date,
    usage_kwh: float | Decimal,
    unit: str | None,
    hours: list[dict[str, Any]],
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO eloverblick.days (
                metering_point_id, day, usage_kwh, unit, scraped_at
            )
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (metering_point_id, day) DO UPDATE SET
                usage_kwh = EXCLUDED.usage_kwh,
                unit = EXCLUDED.unit,
                scraped_at = now()
            """,
            (metering_point_id, day, usage_kwh, unit),
        )
        conn.execute(
            """
            DELETE FROM eloverblick.hours
            WHERE metering_point_id = %s AND local_date = %s
            """,
            (metering_point_id, day),
        )
        for hour in hours:
            conn.execute(
                """
                INSERT INTO eloverblick.hours (
                    metering_point_id, period_start, local_date, local_hour,
                    usage_kwh, unit, quality, scraped_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                """,
                (
                    metering_point_id,
                    hour["period_start"],
                    hour["local_date"],
                    hour["local_hour"],
                    hour["usage_kwh"],
                    hour.get("unit"),
                    hour.get("quality"),
                ),
            )
        _rollup_from_days(conn, metering_point_id, day)
        conn.commit()


def replace_month(
    metering_point_id: str,
    year: int,
    month: int,
    usage_kwh: float | Decimal,
    unit: str | None,
    days: list[dict[str, Any]],
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO eloverblick.months (
                metering_point_id, year, month, usage_kwh, unit, scraped_at
            )
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (metering_point_id, year, month) DO UPDATE SET
                usage_kwh = EXCLUDED.usage_kwh,
                unit = EXCLUDED.unit,
                scraped_at = now()
            """,
            (metering_point_id, year, month, usage_kwh, unit),
        )
        for item in days:
            conn.execute(
                """
                INSERT INTO eloverblick.days (
                    metering_point_id, day, usage_kwh, unit, scraped_at
                )
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (metering_point_id, day) DO UPDATE SET
                    usage_kwh = EXCLUDED.usage_kwh,
                    unit = EXCLUDED.unit,
                    scraped_at = now()
                """,
                (
                    metering_point_id,
                    item["day"],
                    item["usage_kwh"],
                    item.get("unit"),
                ),
            )
        _rollup_year_from_days(conn, metering_point_id, year)
        conn.commit()


def replace_year(
    metering_point_id: str,
    year: int,
    usage_kwh: float | Decimal,
    unit: str | None,
    months: list[dict[str, Any]],
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO eloverblick.years (
                metering_point_id, year, usage_kwh, unit, scraped_at
            )
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (metering_point_id, year) DO UPDATE SET
                usage_kwh = EXCLUDED.usage_kwh,
                unit = EXCLUDED.unit,
                scraped_at = now()
            """,
            (metering_point_id, year, usage_kwh, unit),
        )
        for item in months:
            conn.execute(
                """
                INSERT INTO eloverblick.months (
                    metering_point_id, year, month, usage_kwh, unit, scraped_at
                )
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (metering_point_id, year, month) DO UPDATE SET
                    usage_kwh = EXCLUDED.usage_kwh,
                    unit = EXCLUDED.unit,
                    scraped_at = now()
                """,
                (
                    metering_point_id,
                    year,
                    item["month"],
                    item["usage_kwh"],
                    item.get("unit"),
                ),
            )
        conn.commit()


def replace_hour_prices(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with connect() as conn:
        for item in rows:
            conn.execute(
                """
                INSERT INTO eloverblick.hour_prices (
                    price_area, period_start, local_date, local_hour,
                    price_dkk_mwh, price_eur_mwh, scraped_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (price_area, period_start) DO UPDATE SET
                    local_date = EXCLUDED.local_date,
                    local_hour = EXCLUDED.local_hour,
                    price_dkk_mwh = EXCLUDED.price_dkk_mwh,
                    price_eur_mwh = EXCLUDED.price_eur_mwh,
                    scraped_at = now()
                """,
                (
                    item["price_area"],
                    item["period_start"],
                    item["local_date"],
                    item["local_hour"],
                    item.get("price_dkk_mwh"),
                    item.get("price_eur_mwh"),
                ),
            )
        conn.commit()
    return len(rows)


def list_hour_prices(price_area: str, day: date) -> list[HourPriceRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT price_area, period_start, local_date, local_hour,
                   price_dkk_mwh, price_eur_mwh, scraped_at
            FROM eloverblick.hour_prices
            WHERE price_area = %s AND local_date = %s
            ORDER BY period_start
            """,
            (price_area, day),
        ).fetchall()
    return [_hour_price_row(row) for row in rows]


def hour_price_days(price_area: str, days: list[date]) -> dict[date, int]:
    if not days:
        return {}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT local_date, COUNT(*) AS hour_count
            FROM eloverblick.hour_prices
            WHERE price_area = %s AND local_date = ANY(%s)
            GROUP BY local_date
            """,
            (price_area, days),
        ).fetchall()
    return {row["local_date"]: int(row["hour_count"]) for row in rows}


def ensure_job_state(job_name: str, interval_hours: int) -> JobStateRow:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO eloverblick.job_state (
                job_name, enabled, interval_hours, updated_at
            )
            VALUES (%s, true, %s, now())
            ON CONFLICT (job_name) DO UPDATE SET
                interval_hours = EXCLUDED.interval_hours,
                updated_at = now()
            """,
            (job_name, interval_hours),
        )
        conn.commit()
    state = get_job_state(job_name)
    if state is None:
        raise RuntimeError(f"Failed to create job_state for {job_name}.")
    return state


def get_job_state(job_name: str) -> JobStateRow | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT job_name, enabled, interval_hours, last_run_at,
                   last_success, updated_at
            FROM eloverblick.job_state
            WHERE job_name = %s
            """,
            (job_name,),
        ).fetchone()
    return _job_state_row(row) if row else None


def set_job_enabled(job_name: str, enabled: bool) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE eloverblick.job_state
            SET enabled = %s, updated_at = now()
            WHERE job_name = %s
            """,
            (enabled, job_name),
        )
        conn.commit()


def touch_job_run(job_name: str, success: bool) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE eloverblick.job_state
            SET last_run_at = now(), last_success = %s, updated_at = now()
            WHERE job_name = %s
            """,
            (success, job_name),
        )
        conn.commit()


def insert_job_log(
    *,
    instance: str,
    job_name: str,
    success: bool,
    output: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO eloverblick.job_logs (
                logged_at, instance, job_name, success, output
            )
            VALUES (now(), %s, %s, %s, %s)
            """,
            (instance, job_name, success, output),
        )
        conn.commit()


def list_job_logs(job_name: str | None = None, limit: int = 100) -> list[JobLogRow]:
    with connect() as conn:
        if job_name:
            rows = conn.execute(
                """
                SELECT id, logged_at, instance, job_name, success, output
                FROM eloverblick.job_logs
                WHERE job_name = %s
                ORDER BY logged_at DESC, id DESC
                LIMIT %s
                """,
                (job_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, logged_at, instance, job_name, success, output
                FROM eloverblick.job_logs
                ORDER BY logged_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
    return [_job_log_row(row) for row in rows]


def _rollup_from_days(conn, metering_point_id: str, day: date) -> None:
    conn.execute(
        """
        INSERT INTO eloverblick.months (
            metering_point_id, year, month, usage_kwh, unit, scraped_at
        )
        SELECT
            metering_point_id,
            EXTRACT(YEAR FROM day)::int,
            EXTRACT(MONTH FROM day)::int,
            SUM(usage_kwh),
            MIN(unit),
            now()
        FROM eloverblick.days
        WHERE metering_point_id = %s
          AND EXTRACT(YEAR FROM day) = %s
          AND EXTRACT(MONTH FROM day) = %s
        GROUP BY metering_point_id, EXTRACT(YEAR FROM day), EXTRACT(MONTH FROM day)
        ON CONFLICT (metering_point_id, year, month) DO UPDATE SET
            usage_kwh = EXCLUDED.usage_kwh,
            unit = EXCLUDED.unit,
            scraped_at = now()
        """,
        (metering_point_id, day.year, day.month),
    )
    _rollup_year_from_days(conn, metering_point_id, day.year)


def _rollup_year_from_days(conn, metering_point_id: str, year: int) -> None:
    conn.execute(
        """
        INSERT INTO eloverblick.years (
            metering_point_id, year, usage_kwh, unit, scraped_at
        )
        SELECT
            metering_point_id,
            EXTRACT(YEAR FROM day)::int,
            SUM(usage_kwh),
            MIN(unit),
            now()
        FROM eloverblick.days
        WHERE metering_point_id = %s
          AND EXTRACT(YEAR FROM day) = %s
        GROUP BY metering_point_id, EXTRACT(YEAR FROM day)
        ON CONFLICT (metering_point_id, year) DO UPDATE SET
            usage_kwh = EXCLUDED.usage_kwh,
            unit = EXCLUDED.unit,
            scraped_at = now()
        """,
        (metering_point_id, year),
    )


def _day_row(row: dict[str, Any]) -> DayRow:
    return DayRow(
        metering_point_id=row["metering_point_id"],
        day=row["day"],
        usage_kwh=row["usage_kwh"],
        unit=row["unit"],
        scraped_at=row["scraped_at"],
        hour_count=int(row.get("hour_count") or 0),
    )


def _hour_row(row: dict[str, Any]) -> HourRow:
    return HourRow(
        metering_point_id=row["metering_point_id"],
        period_start=row["period_start"],
        local_date=row["local_date"],
        local_hour=int(row["local_hour"]),
        usage_kwh=row["usage_kwh"],
        unit=row["unit"],
        quality=row["quality"],
        scraped_at=row["scraped_at"],
    )


def _month_row(row: dict[str, Any]) -> MonthRow:
    return MonthRow(
        metering_point_id=row["metering_point_id"],
        year=int(row["year"]),
        month=int(row["month"]),
        usage_kwh=row["usage_kwh"],
        unit=row["unit"],
        scraped_at=row["scraped_at"],
        day_count=int(row.get("day_count") or 0),
    )


def _year_row(row: dict[str, Any]) -> YearRow:
    return YearRow(
        metering_point_id=row["metering_point_id"],
        year=int(row["year"]),
        usage_kwh=row["usage_kwh"],
        unit=row["unit"],
        scraped_at=row["scraped_at"],
        month_count=int(row.get("month_count") or 0),
    )


def _hour_price_row(row: dict[str, Any]) -> HourPriceRow:
    return HourPriceRow(
        price_area=row["price_area"],
        period_start=row["period_start"],
        local_date=row["local_date"],
        local_hour=int(row["local_hour"]),
        price_dkk_mwh=row["price_dkk_mwh"],
        price_eur_mwh=row["price_eur_mwh"],
        scraped_at=row["scraped_at"],
    )


def _job_log_row(row: dict[str, Any]) -> JobLogRow:
    return JobLogRow(
        id=int(row["id"]),
        logged_at=row["logged_at"],
        instance=row["instance"],
        job_name=row["job_name"],
        success=bool(row["success"]),
        output=row["output"],
    )


def _job_state_row(row: dict[str, Any]) -> JobStateRow:
    return JobStateRow(
        job_name=row["job_name"],
        enabled=bool(row["enabled"]),
        interval_hours=int(row["interval_hours"]),
        last_run_at=row["last_run_at"],
        last_success=row["last_success"],
        updated_at=row["updated_at"],
    )
