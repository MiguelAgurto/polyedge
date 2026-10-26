"""Retry NOAA backfill windows that timed out without refetching every day."""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from time import sleep

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.discover_markets import scanner_lock
from polyedge.weather.station import AviationWeatherClient


def retry(settings: Settings) -> dict[str, int]:
    repo = LocalRepository(settings.data_file)
    windows = set()
    for error in repo.data["errors"]:
        message = error["error_message"]
        if message.startswith("METAR "):
            prefix = message.split(":", 1)[0].split()
            if len(prefix) == 3:
                windows.add((prefix[1], prefix[2]))
    client = AviationWeatherClient(timeout=30)
    stats = {"windows": len(windows), "recovered": 0, "observations_created": 0, "errors_count": 0}
    run_id = repo.start_run("weather_history_retry")
    try:
        for index, (ids, day) in enumerate(sorted(windows)):
            if index:
                sleep(0.7)
            end_at = datetime.combine(date.fromisoformat(day) + timedelta(days=1),
                                      datetime.min.time(), timezone.utc).isoformat()
            try:
                rows = client.metars_for_window(set(ids.split(",")), end_at)
                stats["observations_created"] += repo.add_observations(rows)
                stats["recovered"] += 1
                print(json.dumps({"recovered": f"{ids} {day}", "rows": len(rows)}), flush=True)
            except Exception as exc:
                stats["errors_count"] += 1
                repo.error(run_id, type(exc).__name__, f"METAR retry {ids} {day}: {exc}")
                print(json.dumps({"failed": f"{ids} {day}", "error": str(exc)}), flush=True)
    finally:
        repo.finish_run(run_id, status="partial" if stats["errors_count"] else "success", **stats)
        client.close()
    return stats


if __name__ == "__main__":
    try:
        with scanner_lock():
            print(json.dumps({"summary": retry(Settings(storage="local"))}), flush=True)
    except Exception as exc:
        print(json.dumps({"fatal": str(exc)}), file=sys.stderr, flush=True)
        sys.exit(1)
