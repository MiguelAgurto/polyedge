"""Independent Open-Meteo ensemble data and uncalibrated member votes."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx


class OpenMeteoClient:
    MODEL = "gfs_seamless"

    def __init__(self, timeout: float = 15):
        self.http = httpx.Client(timeout=timeout, headers={"User-Agent": "PolyEdge/0.2 (local weather research)"})

    def close(self) -> None:
        self.http.close()

    def geocode(self, city: str) -> dict[str, Any]:
        # The market calls this Seoul, but its named observation station is in Incheon.
        query = "Incheon" if city == "Seoul (Incheon)" else city
        response = self.http.get("https://geocoding-api.open-meteo.com/v1/search", params={
            "name": query, "count": 10, "language": "en", "format": "json",
        })
        response.raise_for_status()
        matches = response.json().get("results") or []
        exact = [row for row in matches if row.get("name", "").casefold() == query.casefold()]
        if not exact:
            raise ValueError(f"Open-Meteo has no exact geocoding match for {city}")
        location = max(exact, key=lambda row: row.get("population") or 0)
        for field in ("latitude", "longitude", "timezone", "country", "name"):
            if not location.get(field):
                raise ValueError(f"Open-Meteo geocoding omitted {field} for {city}")
        return location

    def daily_highs(self, location: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        response = self.http.get("https://ensemble-api.open-meteo.com/v1/ensemble", params={
            "latitude": location["latitude"], "longitude": location["longitude"],
            "timezone": location["timezone"], "daily": "temperature_2m_max",
            "models": self.MODEL, "forecast_days": 7,
        })
        response.raise_for_status()
        payload = response.json()
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        member_keys = sorted(key for key in daily if key.startswith("temperature_2m_max_member"))
        if not dates or len(member_keys) < 10:
            raise ValueError("Open-Meteo returned no usable daily ensemble members")
        rows = []
        for index, day in enumerate(dates):
            members = [daily[key][index] for key in member_keys if index < len(daily[key]) and daily[key][index] is not None]
            if len(members) < 10:
                continue
            rows.append({"target_date": day, "members_c": members})
        return {
            "grid_latitude": payload.get("latitude"),
            "grid_longitude": payload.get("longitude"),
            "grid_timezone": payload.get("timezone"),
        }, rows

    def historical_daily_highs(self, location: dict[str, Any], start_date: str,
                               end_date: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Daily highs from GFS hourly forecasts at a fixed 24-hour lead."""
        response = self.http.get("https://previous-runs-api.open-meteo.com/v1/forecast", params={
            "latitude": location["latitude"], "longitude": location["longitude"],
            "timezone": location["timezone"], "hourly": "temperature_2m_previous_day1",
            "models": self.MODEL, "start_date": start_date, "end_date": end_date,
        })
        response.raise_for_status()
        payload = response.json()
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        values = hourly.get("temperature_2m_previous_day1") or []
        if not times or len(times) != len(values):
            raise ValueError("Open-Meteo returned no usable archived hourly forecasts")
        by_day: dict[str, list[float]] = {}
        for timestamp, value in zip(times, values):
            if value is not None:
                by_day.setdefault(timestamp[:10], []).append(float(value))
        rows = [{"target_date": day, "forecast_high_c": max(samples),
                 "hourly_count": len(samples)}
                for day, samples in sorted(by_day.items()) if len(samples) >= 20]
        return {"grid_latitude": payload.get("latitude"),
                "grid_longitude": payload.get("longitude")}, rows


def member_vote(members_c: list[float], threshold: str, operator: str,
                unit: str, *, whole_degrees: bool) -> tuple[int, int] | None:
    """Count ensemble members meeting a contract, without claiming calibration."""
    if not whole_degrees or not members_c or operator not in {"eq", "gte", "lte", "gt", "lt"}:
        return None
    if unit not in {"C", "F"}:
        return None
    target = Decimal(threshold)
    hits = 0
    for value in members_c:
        temp = Decimal(str(value))
        if unit == "F":
            temp = temp * Decimal(9) / Decimal(5) + Decimal(32)
        rounded = temp.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        hits += {
            "eq": rounded == target,
            "gte": rounded >= target,
            "lte": rounded <= target,
            "gt": rounded > target,
            "lt": rounded < target,
        }[operator]
    return hits, len(members_c)
