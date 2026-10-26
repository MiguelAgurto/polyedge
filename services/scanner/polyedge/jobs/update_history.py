"""Refresh recently completed 24-hour-ahead GFS forecasts each day."""

import json
import sys
from datetime import datetime, timedelta, timezone

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.discover_markets import scanner_lock
from polyedge.weather.ensemble import OpenMeteoClient


def update(settings: Settings, client: OpenMeteoClient | None = None) -> dict[str, int]:
    if settings.storage != "local":
        raise ValueError("Historical weather updates require local storage")
    repo = LocalRepository(settings.data_file)
    stations = {}
    for forecast in reversed(repo.data["forecasts"]):
        station_id = forecast.get("station_id")
        if station_id and forecast.get("location_kind") == "station_coordinates":
            stations.setdefault(station_id, forecast)
    end = datetime.now(timezone.utc).date() - timedelta(days=2)
    start = end - timedelta(days=3)
    stats = {"stations": len(stations), "historical_forecasts": 0, "errors_count": 0}
    run_id = repo.start_run("weather_history_update")
    own_client = client is None
    client = client or OpenMeteoClient(settings.request_timeout)
    try:
        for station_id, forecast in sorted(stations.items()):
            try:
                grid, rows = client.historical_daily_highs(
                    {"latitude": forecast["latitude"], "longitude": forecast["longitude"],
                     "timezone": forecast["timezone"]}, start.isoformat(), end.isoformat())
                for row in rows:
                    repo.upsert_historical_forecast({
                        "station_id": station_id, "model": client.MODEL, "lead_days": 1,
                        "source": "Open-Meteo Previous Runs", "timezone": forecast["timezone"],
                        "grid_latitude": grid["grid_latitude"],
                        "grid_longitude": grid["grid_longitude"], **row,
                    })
                stats["historical_forecasts"] += len(rows)
            except Exception as exc:
                stats["errors_count"] += 1
                repo.error(run_id, type(exc).__name__, f"Archived GFS {station_id}: {exc}")
        cutoff = (end - timedelta(days=35)).isoformat()
        repo.data["historical_forecasts"] = [
            row for row in repo.data["historical_forecasts"] if row["target_date"] >= cutoff]
    finally:
        repo.finish_run(run_id, status="partial" if stats["errors_count"] else "success", **stats)
        if own_client:
            client.close()
    return stats


if __name__ == "__main__":
    try:
        with scanner_lock():
            print(json.dumps({"summary": update(Settings(storage="local"))}), flush=True)
    except Exception as exc:
        print(json.dumps({"fatal": str(exc)}), file=sys.stderr, flush=True)
        sys.exit(1)
