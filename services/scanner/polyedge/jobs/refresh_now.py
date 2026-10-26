"""Refresh every live input and then recompute local signals on demand."""

import json
import sys
from time import sleep

from polyedge.config import Settings
from polyedge.jobs.collect_forecasts import collect as collect_forecasts
from polyedge.jobs.collect_observations import collect as collect_observations
from polyedge.jobs.discover_markets import scan, scanner_lock
from polyedge.jobs.generate_signals import generate
from polyedge.jobs.collect_traders import collect as collect_traders


def refresh(settings: Settings) -> dict:
    # Give an already-running watcher scan a chance to finish.
    for attempt in range(30):
        try:
            with scanner_lock():
                results = {"markets": scan(settings, mode="all")}
                results["forecasts"] = collect_forecasts(settings)
                results["observations"] = collect_observations(settings)
                results["signals"] = generate(settings)
                results["traders"] = collect_traders(settings)
                return results
        except RuntimeError as exc:
            if str(exc) != "another scanner job is running" or attempt == 29:
                raise
            sleep(2)
    raise RuntimeError("the local scanner did not become available")


if __name__ == "__main__":
    try:
        result = refresh(Settings(storage="local"))
        print(json.dumps({"summary": result}), flush=True)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr, flush=True)
        sys.exit(1)
