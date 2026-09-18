"""OOP client for the ElOverblik Customer API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any

from script.exceptions import AddressSelectionError, ApiError
from script.models import Aggregation, MeteringPoint, TimeSeries, as_date_str
from script.settings import Settings

MAX_METERING_POINTS_PER_REQUEST = 10


class CustomerApi:
    """Talks to the Customer API as one private Danish electricity customer.

    Create with CustomerApi.from_env() so the refresh token is taken from
    ELOVERBLIK_TOKEN. The short-lived data-access token is fetched once and
    reused on this instance.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._access_token: str | None = None
        self._selected_address: MeteringPoint | None = None

    @classmethod
    def from_env(cls) -> CustomerApi:
        """Build a client from ELOVERBLIK_TOKEN."""
        return cls(Settings.from_env())

    def is_alive(self) -> bool:
        """Return True when the API reports that it is operating normally."""
        payload = self._request("GET", "/isalive", authorized=False)
        if isinstance(payload, bool):
            return payload
        if isinstance(payload, dict) and "result" in payload:
            return bool(payload["result"])
        return bool(payload)

    def access_token(self) -> str:
        """Return the cached 24-hour data-access token, fetching it if needed."""
        if not self._access_token:
            self._access_token = self._fetch_access_token()
        return self._access_token

    def metering_points(self, include_all: bool = False) -> list[MeteringPoint]:
        """List metering points linked to the customer."""
        query = f"?includeAll={'true' if include_all else 'false'}"
        payload = self._request("GET", f"/meteringpoints/meteringpoints{query}")
        rows = _result_list(payload)
        return [MeteringPoint.from_api(row) for row in rows if isinstance(row, dict)]

    def addresses(self, include_all: bool = False) -> list[MeteringPoint]:
        """Return every address on this API key, with consumer name and status.

        Status is ``active`` or ``moved_out`` (see MeteringPoint.status).
        """
        return self.metering_points(include_all=include_all)

    @property
    def selected_address(self) -> MeteringPoint | None:
        """Address used for usage calls until another one is selected."""
        return self._selected_address

    def select_address(
        self,
        address: str | MeteringPoint | None = None,
        *,
        include_all: bool = False,
    ) -> MeteringPoint:
        """Choose the address used from here on for usage requests.

        With no argument, the single active (not moved-out) address is selected.
        Pass a metering point id, street name, consumer name, or MeteringPoint
        to pick an alternative — including a moved-out address.
        """
        points = self.addresses(include_all=include_all)
        if not points:
            raise AddressSelectionError("No addresses are attached to this API key.")

        if address is None:
            chosen = _unique_active_address(points)
        elif isinstance(address, MeteringPoint):
            chosen = _match_address(points, address.metering_point_id)
        else:
            chosen = _match_address(points, str(address))

        self._selected_address = chosen
        return chosen

    def time_series(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        aggregation: Aggregation | str,
        metering_point_ids: list[str] | str | None = None,
    ) -> list[TimeSeries]:
        """Fetch time series for the selected address, or explicit meter ids.

        date_from is inclusive and date_to is exclusive (YYYY-MM-DD).
        At most 10 metering point IDs may be requested at once.
        """
        ids = _normalize_ids(metering_point_ids or self._selected_meter_id())
        agg = Aggregation(aggregation)
        path = (
            f"/meterdata/gettimeseries/"
            f"{as_date_str(date_from)}/{as_date_str(date_to)}/{agg.value}"
        )
        payload = self._request(
            "POST",
            path,
            body={"meteringPoints": {"meteringPoint": ids}},
        )
        rows = _result_list(payload)
        return [TimeSeries.from_api(row, agg) for row in rows if isinstance(row, dict)]

    def hourly(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        metering_point_ids: list[str] | str | None = None,
    ) -> list[TimeSeries]:
        return self.time_series(date_from, date_to, Aggregation.HOUR, metering_point_ids)

    def daily(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        metering_point_ids: list[str] | str | None = None,
    ) -> list[TimeSeries]:
        return self.time_series(date_from, date_to, Aggregation.DAY, metering_point_ids)

    def monthly(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        metering_point_ids: list[str] | str | None = None,
    ) -> list[TimeSeries]:
        return self.time_series(date_from, date_to, Aggregation.MONTH, metering_point_ids)

    def yearly(
        self,
        date_from: date | datetime | str,
        date_to: date | datetime | str,
        metering_point_ids: list[str] | str | None = None,
    ) -> list[TimeSeries]:
        return self.time_series(date_from, date_to, Aggregation.YEAR, metering_point_ids)

    def _selected_meter_id(self) -> str:
        if self._selected_address is None:
            raise AddressSelectionError(
                "No address is selected. Call select_address() first, "
                "or pass metering_point_ids."
            )
        return self._selected_address.metering_point_id

    def _fetch_access_token(self) -> str:
        payload = self._request(
            "GET",
            "/token",
            authorized=False,
            extra_headers={"Authorization": f"Bearer {self.settings.refresh_token}"},
        )
        token = payload.get("result") if isinstance(payload, dict) else payload
        if not token or not isinstance(token, str):
            raise ApiError("Token endpoint did not return an access token.", body=payload)
        return token

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        authorized: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.settings.base_url}{path}"
        headers = {
            "Accept": "application/json",
            "api-version": self.settings.api_version,
        }
        if authorized:
            headers["Authorization"] = f"Bearer {self.access_token()}"
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                if not raw:
                    return None
                content_type = response.headers.get("Content-Type", "")
                text = raw.decode("utf-8")
                if "json" in content_type or text[:1] in "{[":
                    return json.loads(text)
                if text.lower() in {"true", "false"}:
                    return text.lower() == "true"
                return text
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            parsed: Any = error_body
            try:
                parsed = json.loads(error_body) if error_body else None
            except json.JSONDecodeError:
                parsed = error_body
            raise ApiError(
                f"{method} {path} failed with HTTP {exc.code}: {exc.reason}",
                status_code=exc.code,
                body=parsed,
            ) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"{method} {path} failed: {exc.reason}") from exc


def _result_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        result = payload.get("result")
        if result is None:
            return []
        if isinstance(result, list):
            return result
        return [result]
    return []


def _normalize_ids(metering_point_ids: list[str] | str) -> list[str]:
    if isinstance(metering_point_ids, str):
        ids = [metering_point_ids]
    else:
        ids = list(metering_point_ids)
    ids = [item.strip() for item in ids if item and item.strip()]
    if not ids:
        raise ApiError("At least one metering point ID is required.")
    if len(ids) > MAX_METERING_POINTS_PER_REQUEST:
        raise ApiError(
            f"At most {MAX_METERING_POINTS_PER_REQUEST} metering point IDs "
            "may be requested at once."
        )
    return ids


def _unique_active_address(points: list[MeteringPoint]) -> MeteringPoint:
    active = [point for point in points if point.is_active]
    if len(active) == 1:
        return active[0]
    if not active:
        listing = _format_address_list(points)
        raise AddressSelectionError(
            "No active address is attached to this API key. "
            "Pass an alternative to select_address(). "
            f"Available addresses:\n{listing}"
        )
    listing = _format_address_list(active)
    raise AddressSelectionError(
        "More than one active address is attached to this API key. "
        "Pass the id, street, or name to select_address(). "
        f"Active addresses:\n{listing}"
    )


def _match_address(points: list[MeteringPoint], query: str) -> MeteringPoint:
    matches = [point for point in points if point.matches(query)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        listing = _format_address_list(points)
        raise AddressSelectionError(
            f"No address matched {query!r}. Available addresses:\n{listing}"
        )
    listing = _format_address_list(matches)
    raise AddressSelectionError(
        f"Address query {query!r} matched more than one address:\n{listing}"
    )


def _format_address_list(points: list[MeteringPoint]) -> str:
    lines = []
    for point in points:
        name = point.name or "(no name)"
        lines.append(
            f"  {point.metering_point_id}  {name}  "
            f"{point.address}  [{point.status}]"
        )
    return "\n".join(lines)
