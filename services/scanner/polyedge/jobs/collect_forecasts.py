"""Collect and archive independent ensemble forecasts for active local markets."""

import argparse
import json
import logging
import math
import sys
from collections import defaultdict

from polyedge.config import Settings
from polyedge.database.local import LocalRepository, utcnow
from polyedge.jobs.discover_markets import JsonFormatter, scanner_lock
from polyedge.weather.ensemble import OpenMeteoClient, member_vote
from polyedge.weather.parser import station_id_from_source
from polyedge.weather.station import AviationWeatherClient

log = logging.getLogger("polyedge.forecasts")


def grid_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return round(6371 * 2 * math.asin(min(1, math.sqrt(a))), 1)


def collect(settings: Settings, client: OpenMeteoClient | None = None,
            station_client: AviationWeatherClient | None = None) -> dict[str, int]:
    if settings.storage != "local":
        raise ValueError("Phase 2 forecast collection currently requires local storage")
    repo = LocalRepository(settings.data_file)
    repo.expire_markets()
    groups = defaultdict(list)
    for market in repo.data["markets"]:
        if (market["market_status"] == "active" and
                market["market_type"] == "daily_max_temperature" and
                market.get("city") and market.get("target_date")):
            station_id = market.get("station_id") or station_id_from_source(market.get("resolution_source"))
            if station_id:
                market["station_id"] = station_id
            groups[(market["city"], station_id)].append(market)
    stats = {"stations_matched": 0, "forecasts_created": 0, "votes_updated": 0, "errors_count": 0}
    run_id = repo.start_run("forecasts")
    own_client = client is None
    own_station_client = station_client is None
    client = client or OpenMeteoClient(settings.request_timeout)
    station_client = station_client or AviationWeatherClient(settings.request_timeout)
    try:
        try:
            stations = station_client.station_info({station_id for _, station_id in groups if station_id})
        except Exception as exc:
            stats["errors_count"] += 1
            repo.error(run_id, type(exc).__name__, f"NOAA station lookup: {exc}")
            log.exception("station_lookup_error", extra={"error_type": type(exc).__name__})
            return stats
        for (city, station_id), markets in groups.items():
            try:
                if not station_id or station_id not in stations:
                    raise ValueError(f"No NOAA station metadata for {city} ({station_id or 'missing ID'})")
                station = stations[station_id]
                city_location = client.geocode(city)
                if city_location.get("country_code") != station["country_code"]:
                    raise ValueError(f"NOAA station and city countries differ for {city} ({station_id})")
                location = {
                    "name": station["station_name"], "country": city_location["country"],
                    "latitude": station["latitude"], "longitude": station["longitude"],
                    "timezone": city_location["timezone"],
                }
                grid, rows = client.daily_highs(location)
                if grid["grid_latitude"] is None or grid["grid_longitude"] is None:
                    raise ValueError(f"Open-Meteo omitted its grid coordinates for {city}")
                stats["stations_matched"] += 1
                requested_dates = {market["target_date"] for market in markets}
                for row in rows:
                    if row["target_date"] not in requested_dates:
                        continue
                    collected_at = utcnow()
                    forecast_id = repo.add_forecast({
                        "city": city, "collected_at": collected_at,
                        "provider": "Open-Meteo", "model": client.MODEL,
                        "location_kind": "station_coordinates", "station_id": station_id,
                        "location_name": location["name"], "country": location["country"],
                        "latitude": location["latitude"], "longitude": location["longitude"],
                        "grid_distance_km": grid_distance_km(location["latitude"], location["longitude"],
                                                              grid["grid_latitude"], grid["grid_longitude"]),
                        "timezone": location["timezone"], **grid, **row,
                    })
                    stats["forecasts_created"] += 1
                    for market in markets:
                        if market["target_date"] != row["target_date"] or not market.get("threshold"):
                            continue
                        # The contract's explicit whole-degree rule is needed for bracket counting.
                        whole_degrees = "whole degrees" in (market.get("resolution_rules") or "").lower()
                        vote = member_vote(row["members_c"], market["threshold"],
                                           market.get("comparison_operator"),
                                           market.get("temperature_unit"),
                                           whole_degrees=whole_degrees)
                        if vote is None:
                            continue
                        repo.upsert_ensemble_vote({
                            "market_id": market["id"], "forecast_id": forecast_id,
                            "collected_at": collected_at,
                            "yes_members": vote[0], "total_members": vote[1],
                            "method": "rounded_whole_degree_ensemble_member_count",
                        })
                        stats["votes_updated"] += 1
                if not any(row["target_date"] in requested_dates for row in rows):
                    raise ValueError(f"Open-Meteo has no current forecast for {city} target dates")
            except Exception as exc:
                stats["errors_count"] += 1
                repo.error(run_id, type(exc).__name__, f"{city}: {exc}")
                log.exception("forecast_error", extra={"error_type": type(exc).__name__})
    finally:
        repo.finish_run(run_id, status="partial" if stats["errors_count"] else "success", **stats)
        if own_client:
            client.close()
        if own_station_client:
            station_client.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Open-Meteo daily high ensemble forecasts")
    parser.parse_args(argv)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        with scanner_lock():
            stats = collect(Settings(storage="local"))
        print(json.dumps({"summary": stats}))
        return 0 if stats["errors_count"] == 0 else 1
    except Exception:
        log.exception("forecast_job_fatal")
        return 1


if __name__ == "__main__":
    sys.exit(main())
