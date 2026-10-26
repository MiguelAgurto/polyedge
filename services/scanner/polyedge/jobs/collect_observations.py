"""Archive recent airport temperature observations from NOAA Aviation Weather."""

import argparse
import json
import logging
import sys
from time import sleep

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.discover_markets import JsonFormatter, scanner_lock
from polyedge.weather.parser import station_id_from_source
from polyedge.weather.station import AviationWeatherClient

log = logging.getLogger("polyedge.observations")


def collect(settings: Settings, client: AviationWeatherClient | None = None,
            pause_seconds: float = 0.65) -> dict[str, int]:
    if settings.storage != "local":
        raise ValueError("Phase 2 observation collection currently requires local storage")
    repo = LocalRepository(settings.data_file)
    repo.expire_markets()
    station_ids = {
        market.get("station_id") or station_id_from_source(market.get("resolution_source"))
        for market in repo.data["markets"]
        if market["market_status"] == "active" and market["market_type"] == "daily_max_temperature"
    } - {None}
    stats = {"stations_checked": 0, "observations_created": 0, "errors_count": 0}
    run_id = repo.start_run("observations")
    own_client = client is None
    client = client or AviationWeatherClient(settings.request_timeout)
    try:
        for index, station_id in enumerate(sorted(station_ids)):
            if index and pause_seconds:
                sleep(pause_seconds)
            try:
                rows = client.metars(station_id, hours=24)
                stats["stations_checked"] += 1
                stats["observations_created"] += repo.add_observations(rows)
            except Exception as exc:
                stats["errors_count"] += 1
                repo.error(run_id, type(exc).__name__, f"{station_id}: {exc}")
                log.exception("observation_error", extra={"error_type": type(exc).__name__})
    finally:
        repo.finish_run(run_id, status="partial" if stats["errors_count"] else "success", **stats)
        if own_client:
            client.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive recent NOAA airport temperature observations")
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
        log.exception("observation_job_fatal")
        return 1


if __name__ == "__main__":
    sys.exit(main())
