"""Generate local, read-only YES/NO buy decisions after each market update."""

import argparse
import json
import sys
from collections import defaultdict

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.discover_markets import scanner_lock
from polyedge.weather.signals import decide, station_validation


def generate(settings: Settings) -> dict[str, int]:
    if settings.storage != "local":
        raise ValueError("Signals currently require local storage")
    repo = LocalRepository(settings.data_file)
    repo.expire_markets()
    active = [market for market in repo.data["markets"]
              if market["market_status"] == "active" and
              market["market_type"] == "daily_max_temperature"]
    historical: dict[str, list] = defaultdict(list)
    observations: dict[str, list] = defaultdict(list)
    forecasts: dict[tuple[str, str], dict] = {}
    for row in repo.data["historical_forecasts"]:
        historical[row["station_id"]].append(row)
    for row in repo.data["observations"]:
        observations[row["station_id"]].append(row)
    for row in repo.data["forecasts"]:
        station = row.get("station_id")
        if station and row.get("location_kind") == "station_coordinates":
            key = (station, row["target_date"])
            if key not in forecasts or row["collected_at"] > forecasts[key]["collected_at"]:
                forecasts[key] = row
    validations = {}
    for station in {market.get("station_id") for market in active} - {None}:
        station_forecast = next((row for (sid, _), row in forecasts.items() if sid == station), None)
        if station_forecast:
            validations[station] = station_validation(
                historical[station], observations[station], station_forecast["timezone"])
    rows = [decide(market, forecasts.get((market.get("station_id"), market.get("target_date"))),
                   validations.get(market.get("station_id")),
                   repo.data["tokens"], repo.data["snapshots"])
            for market in active]
    repo.replace_signals(rows)
    return {"markets": len(rows), "buy_yes": sum(r["signal"] == "BUY YES" for r in rows),
            "buy_no": sum(r["signal"] == "BUY NO" for r in rows),
            "no_buy": sum(r["signal"] == "NO BUY" for r in rows),
            "stations_validated": sum(v["history_days"] >= 21 and v["training_days"] >= 16 and
                                      v["holdout_days"] >= 5 and v["holdout_mae_c"] is not None and
                                      v["holdout_mae_c"] <= 3 and
                                      v["holdout_80pct_coverage"] >= 0.5
                                      for v in validations.values())}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Update local weather-market signals").parse_args(argv)
    try:
        with scanner_lock():
            print(json.dumps({"summary": generate(Settings(storage="local"))}), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"fatal": str(exc)}), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
