"""Run the local Polymarket scanner at a steady, single-process cadence."""

import argparse
import fcntl
import json
import logging
import signal
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from time import monotonic

from polyedge.config import Settings
from polyedge.jobs.collect_forecasts import collect as collect_forecasts
from polyedge.jobs.collect_observations import collect as collect_observations
from polyedge.jobs.collect_traders import collect as collect_traders
from polyedge.jobs.generate_signals import generate as generate_signals
from polyedge.jobs.update_history import update as update_history
from polyedge.jobs.discover_markets import JsonFormatter, scan, scanner_lock

log = logging.getLogger("polyedge.watcher")


@contextmanager
def watcher_lock():
    path = Path("/tmp/polyedge-local-watcher.lock")
    with path.open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("the local scanner is already running") from exc
        yield


def run_local(settings: Settings, stop: threading.Event,
              discovery_seconds: float = 1800, snapshot_seconds: float = 300,
              forecast_seconds: float = 3600, observation_seconds: float = 3600,
              history_seconds: float = 86400) -> None:
    next_discovery = monotonic()
    next_snapshot = monotonic()
    next_forecast = monotonic()
    next_observation = monotonic()
    next_history = monotonic()
    while not stop.is_set():
        now = monotonic()
        if now >= next_discovery:
            mode = "all"
        elif now >= next_snapshot:
            mode = "snapshots"
        else:
            stop.wait(min(next_discovery, next_snapshot) - now)
            continue
        try:
            with scanner_lock():
                stats = scan(settings, mode=mode)
                if settings.storage == "local" and monotonic() >= next_forecast:
                    forecast_stats = collect_forecasts(settings)
                    print(json.dumps({"mode": "forecasts", "summary": forecast_stats}), flush=True)
                    next_forecast = monotonic() + forecast_seconds
                if settings.storage == "local" and monotonic() >= next_observation:
                    observation_stats = collect_observations(settings)
                    print(json.dumps({"mode": "observations", "summary": observation_stats}), flush=True)
                    next_observation = monotonic() + observation_seconds
                if settings.storage == "local" and monotonic() >= next_history:
                    history_stats = update_history(settings)
                    print(json.dumps({"mode": "weather_history_update", "summary": history_stats}), flush=True)
                    next_history = monotonic() + history_seconds
                if settings.storage == "local":
                    signal_stats = generate_signals(settings)
                    print(json.dumps({"mode": "signals", "summary": signal_stats}), flush=True)
                    trader_stats = collect_traders(settings)
                    print(json.dumps({"mode": "traders", "summary": trader_stats}), flush=True)
            print(json.dumps({"mode": mode, "summary": stats}), flush=True)
        except RuntimeError as exc:
            log.warning("scan_skipped", extra={"error": str(exc)})
        except Exception:
            log.exception("scan_failed")
        completed = monotonic()
        if mode == "all":
            next_discovery = completed + discovery_seconds
            next_snapshot = completed + snapshot_seconds
        else:
            next_snapshot = completed + snapshot_seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep local weather market data up to date")
    parser.add_argument("--discovery-minutes", type=float, default=30)
    parser.add_argument("--snapshot-minutes", type=float, default=5)
    parser.add_argument("--forecast-minutes", type=float, default=60)
    parser.add_argument("--observation-minutes", type=float, default=60)
    args = parser.parse_args(argv)
    if (args.discovery_minutes <= 0 or args.snapshot_minutes <= 0 or
            args.forecast_minutes <= 0 or args.observation_minutes <= 0):
        parser.error("scan intervals must be positive")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        with watcher_lock():
            print(
                f"Local scanning started: markets every {args.discovery_minutes:g} minutes, "
                f"prices every {args.snapshot_minutes:g} minutes, "
                f"forecasts every {args.forecast_minutes:g} minutes, "
                f"airport observations every {args.observation_minutes:g} minutes.",
                flush=True,
            )
            run_local(Settings(storage="local"), stop,
                      discovery_seconds=args.discovery_minutes * 60,
                      snapshot_seconds=args.snapshot_minutes * 60,
                      forecast_seconds=args.forecast_minutes * 60,
                      observation_seconds=args.observation_minutes * 60)
        return 0
    except Exception:
        log.exception("watcher_fatal")
        return 1


if __name__ == "__main__":
    sys.exit(main())
