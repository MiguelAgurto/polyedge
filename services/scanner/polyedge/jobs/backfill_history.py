"""Backfill bounded public weather history for station-level model validation."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from time import sleep

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.discover_markets import scanner_lock
from polyedge.weather.ensemble import OpenMeteoClient
from polyedge.weather.station import AviationWeatherClient


def backfill(settings: Settings, days: int = 28, pause_seconds: float = 0.65) -> dict[str, int]:
    if settings.storage != "local" or not 14 <= days <= 28:
        raise ValueError("Local backfill requires 14–28 days")
    repo = LocalRepository(settings.data_file)
    # Two days behind UTC guarantees that all local calendar days have ended.
    end = datetime.now(timezone.utc).date() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    stations = {}
    for forecast in reversed(repo.data["forecasts"]):
        station_id = forecast.get("station_id")
        if station_id and forecast.get("location_kind") == "station_coordinates":
            stations.setdefault(station_id, forecast)
    if not stations:
        raise ValueError("Collect station-matched forecasts before backfilling history")
    stats = {"stations": len(stations), "historical_forecasts": 0,
             "observations_created": 0, "errors_count": 0}
    weather = OpenMeteoClient(settings.request_timeout)
    aviation = AviationWeatherClient(settings.request_timeout)
    run_id = repo.start_run("weather_history")
    try:
        for station_id, forecast in sorted(stations.items()):
            try:
                location = {"latitude": forecast["latitude"], "longitude": forecast["longitude"],
                            "timezone": forecast["timezone"]}
                grid, rows = weather.historical_daily_highs(location, start.isoformat(), end.isoformat())
                for row in rows:
                    repo.upsert_historical_forecast({
                        "station_id": station_id, "model": weather.MODEL, "lead_days": 1,
                        "source": "Open-Meteo Previous Runs", "timezone": forecast["timezone"],
                        "grid_latitude": grid["grid_latitude"],
                        "grid_longitude": grid["grid_longitude"], **row,
                    })
                stats["historical_forecasts"] += len(rows)
                print(json.dumps({"station": station_id, "forecast_days": len(rows)}), flush=True)
            except Exception as exc:
                stats["errors_count"] += 1
                repo.error(run_id, type(exc).__name__, f"Archived GFS {station_id}: {exc}")
                print(json.dumps({"station": station_id, "error": str(exc)}), flush=True)
        repo.save()
        ids = sorted(stations)
        groups = [set(ids[index:index + 2]) for index in range(0, len(ids), 2)]
        requests = 0
        for offset in range(-1, days):
            utc_day = start + timedelta(days=offset)
            end_at = datetime.combine(utc_day + timedelta(days=1), datetime.min.time(), timezone.utc).isoformat()
            for group in groups:
                if requests and pause_seconds:
                    sleep(pause_seconds)
                requests += 1
                try:
                    rows = aviation.metars_for_window(group, end_at)
                    stats["observations_created"] += repo.add_observations(rows)
                except Exception as exc:
                    stats["errors_count"] += 1
                    repo.error(run_id, type(exc).__name__, f"METAR {','.join(sorted(group))} {utc_day}: {exc}")
            if offset % 5 == 0 or offset == days - 1:
                repo.save()
                print(json.dumps({"through_utc_day": utc_day.isoformat(),
                                  "observations_created": stats["observations_created"],
                                  "errors_count": stats["errors_count"]}), flush=True)
    finally:
        repo.finish_run(run_id, status="partial" if stats["errors_count"] else "success", **stats)
        weather.close()
        aviation.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill 28 days of airport and GFS history")
    parser.add_argument("--days", type=int, default=28)
    args = parser.parse_args(argv)
    try:
        with scanner_lock():
            stats = backfill(Settings(storage="local"), args.days)
        print(json.dumps({"summary": stats}), flush=True)
        return 0 if stats["errors_count"] == 0 else 1
    except Exception as exc:
        print(json.dumps({"fatal": str(exc)}), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
