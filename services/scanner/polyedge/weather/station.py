"""Read public NOAA Aviation Weather station metadata for explicit ICAO IDs."""

from typing import Any
from datetime import datetime, timezone

import httpx


class AviationWeatherClient:
    def __init__(self, timeout: float = 15):
        self.http = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "PolyEdge/0.2 (local weather station research)"},
        )

    def close(self) -> None:
        self.http.close()

    def station_info(self, station_ids: set[str]) -> dict[str, dict[str, Any]]:
        if not station_ids:
            return {}
        response = self.http.get(
            "https://aviationweather.gov/api/data/stationinfo",
            params={"ids": ",".join(sorted(station_ids)), "format": "json"},
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("NOAA station information was not a list")
        stations = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("icaoId") not in station_ids:
                continue
            if not all(row.get(field) is not None for field in ("lat", "lon", "site", "country")):
                continue
            stations[row["icaoId"]] = {
                "station_id": row["icaoId"], "station_name": row["site"],
                "latitude": float(row["lat"]), "longitude": float(row["lon"]),
                "country_code": row["country"],
            }
        return stations

    def metars(self, station_id: str, hours: int = 24) -> list[dict[str, Any]]:
        response = self.http.get(
            "https://aviationweather.gov/api/data/metar",
            params={"ids": station_id, "format": "json", "hours": hours},
        )
        return self._parse_metars(response, {station_id})

    def metars_for_window(self, station_ids: set[str], end_at: str,
                          hours: int = 24) -> list[dict[str, Any]]:
        if not station_ids:
            return []
        response = self.http.get(
            "https://aviationweather.gov/api/data/metar",
            params={"ids": ",".join(sorted(station_ids)), "format": "json",
                    "date": end_at, "hours": hours},
        )
        return self._parse_metars(response, station_ids)

    @staticmethod
    def _parse_metars(response: httpx.Response, station_ids: set[str]) -> list[dict[str, Any]]:
        response.raise_for_status()
        if response.status_code == 204:
            return []
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("NOAA METAR response was not a list")
        if len(rows) >= 400:
            raise ValueError("NOAA METAR result reached the 400-row cap; use a smaller station group")
        observations = []
        for row in rows:
            if not isinstance(row, dict) or row.get("icaoId") not in station_ids:
                continue
            temp = row.get("temp")
            timestamp = row.get("obsTime")
            if isinstance(temp, bool) or not isinstance(temp, (int, float)):
                continue
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                continue
            if not -90 <= temp <= 60:
                continue
            observations.append({
                "station_id": row["icaoId"],
                "observed_at": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                "temp_c": float(temp), "raw_ob": row.get("rawOb") or "",
                "report_type": row.get("metarType"),
                "source": "NOAA Aviation Weather METAR",
            })
        return observations
