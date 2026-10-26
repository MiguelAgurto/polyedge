"""Conservative, testable weather-market decisions from station history and live asks."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean, median, pstdev
from typing import Any
from zoneinfo import ZoneInfo


MIN_HISTORY = 21
MIN_TRAIN = 16
HOLDOUT_DAYS = 7
MIN_OBSERVATION_HOURS = 18
MIN_BOOK_SHARES = 20
MIN_BOOK_DOLLARS = 5
MIN_EDGE = 0.05


def contract_hit(temp_c: float, market: dict[str, Any]) -> bool | None:
    if "whole degrees" not in (market.get("resolution_rules") or "").lower():
        return None
    unit, operator = market.get("temperature_unit"), market.get("comparison_operator")
    if unit not in {"C", "F"} or operator not in {"eq", "gte", "lte", "gt", "lt"}:
        return None
    try:
        target = Decimal(str(market["threshold"]))
    except (TypeError, ValueError):
        return None
    value = Decimal(str(temp_c))
    if unit == "F":
        value = value * Decimal(9) / Decimal(5) + Decimal(32)
    rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {"eq": rounded == target, "gte": rounded >= target, "lte": rounded <= target,
            "gt": rounded > target, "lt": rounded < target}[operator]


def station_days(observations: list[dict[str, Any]], timezone_name: str) -> dict[str, dict[str, float]]:
    zone = ZoneInfo(timezone_name)
    grouped: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for row in observations:
        instant = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
        local = instant.astimezone(zone)
        grouped[local.date().isoformat()].append((local, float(row["temp_c"])))
    result = {}
    for day, samples in grouped.items():
        hours = {sample[0].replace(minute=0, second=0, microsecond=0) for sample in samples}
        duration = (max(s[0] for s in samples) - min(s[0] for s in samples)).total_seconds() / 3600
        if len(hours) >= MIN_OBSERVATION_HOURS and duration >= 20:
            result[day] = {"observed_high_c": max(value for _, value in samples),
                           "observation_hours": len(hours)}
    return result


def station_validation(history: list[dict[str, Any]],
                       station_observations: list[dict[str, Any]], timezone_name: str) -> dict[str, Any]:
    outcomes = station_days(station_observations, timezone_name)
    pairs = sorted([
        {"date": row["target_date"], "forecast": float(row["forecast_high_c"]),
         "observed": outcomes[row["target_date"]]["observed_high_c"],
         "hours": outcomes[row["target_date"]]["observation_hours"]}
        for row in history if row["target_date"] in outcomes and row.get("hourly_count", 0) >= 20
    ], key=lambda row: row["date"])
    holdout = pairs[-HOLDOUT_DAYS:]
    train = pairs[:-HOLDOUT_DAYS]
    errors = [row["observed"] - row["forecast"] for row in train]
    tests = []
    for row in holdout:
        if len(errors) >= MIN_TRAIN:
            bias = median(errors)
            sorted_errors = sorted(errors)
            low = sorted_errors[max(0, math.floor(0.1 * (len(errors) - 1)))]
            high = sorted_errors[min(len(errors) - 1, math.ceil(0.9 * (len(errors) - 1)))]
            tests.append({"date": row["date"], "abs_error_c": abs(row["observed"] - row["forecast"] - bias),
                          "covered": low <= row["observed"] - row["forecast"] <= high})
        errors.append(row["observed"] - row["forecast"])
    residuals = [row["observed"] - row["forecast"] for row in pairs]
    return {"history_days": len(pairs), "training_days": len(train), "holdout_days": len(tests),
            "holdout_mae_c": round(mean(row["abs_error_c"] for row in tests), 2) if tests else None,
            "holdout_80pct_coverage": round(mean(row["covered"] for row in tests), 2) if tests else None,
            "median_bias_c": round(median(residuals), 2) if residuals else None,
            "residuals_c": residuals}


def wilson_interval(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0, 1
    p = hits / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - half), min(1, center + half)


def latest_snapshot(snapshots: list[dict[str, Any]], token_id: str) -> dict[str, Any] | None:
    return max((s for s in snapshots if s["token_id"] == token_id),
               key=lambda s: s["captured_at"], default=None)


def ask_quote(snapshot: dict[str, Any] | None) -> tuple[float, float] | None:
    if not snapshot:
        return None
    asks = (snapshot.get("raw_orderbook") or {}).get("asks") or []
    levels = [(float(level["price"]), float(level["size"])) for level in asks
              if float(level["price"]) > 0 and float(level["size"]) > 0]
    if not levels:
        return None
    best = min(price for price, _ in levels)
    size = sum(size for price, size in levels if price == best)
    if abs(best - float(snapshot.get("best_ask") or 0)) > 0.00001:
        return None
    return best, size


def market_fee_rate(market: dict[str, Any]) -> float | None:
    metadata = market.get("raw_metadata") or {}
    schedule = metadata.get("feeSchedule") or {}
    if (metadata.get("feesEnabled") is True and metadata.get("feeType") == "weather_fees" and
            schedule.get("exponent") == 1 and schedule.get("takerOnly") is True and
            isinstance(schedule.get("rate"), (int, float)) and 0 <= schedule["rate"] <= 0.1):
        return float(schedule["rate"])
    return None


def decide(market: dict[str, Any], forecast: dict[str, Any] | None,
           validation: dict[str, Any] | None, tokens: list[dict[str, Any]],
           snapshots: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    base: dict[str, Any] = {"market_id": market["id"], "station_id": market.get("station_id"),
                            "target_date": market.get("target_date"), "generated_at": now.isoformat(),
                            "signal": "NO BUY", "reason": "Insufficient verified information.",
                            "yes_probability": None, "yes_range_low": None, "yes_range_high": None,
                            "best_side": None, "best_ask": None, "fee_per_share": None,
                            "conservative_edge": None, "quote_size": None,
                            "model_shift_c": None,
                            "validation": {key: value for key, value in (validation or {}).items()
                                           if key != "residuals_c"}}
    if not forecast or not validation:
        base["reason"] = "Waiting for station forecast and historical weather checks."
        return base
    if validation["history_days"] < MIN_HISTORY or validation["training_days"] < MIN_TRAIN or validation["holdout_days"] < 5:
        base["reason"] = "Too few complete airport days to trust this estimate."
        return base
    if validation["holdout_mae_c"] is None or validation["holdout_mae_c"] > 3 or validation["holdout_80pct_coverage"] < 0.5:
        base["reason"] = "Recent forecast checks were not accurate enough for a buy call."
        return base
    forecast_age = (now - datetime.fromisoformat(forecast["collected_at"].replace("Z", "+00:00"))).total_seconds()
    if not -60 <= forecast_age <= 3 * 3600:
        base["reason"] = "The station forecast needs refreshing."
        return base
    members = forecast.get("members_c") or []
    if len(members) < 20 or forecast.get("grid_distance_km", 999) > 35:
        base["reason"] = "The weather model does not cover this airport closely enough."
        return base
    forecast_high = mean(members)
    # Stress both the model spread and a one-degree station/settlement mismatch.
    shift = max(1.0, 1.64 * pstdev(members))
    scenarios = [[contract_hit(forecast_high + residual + offset, market)
                  for residual in validation["residuals_c"]] for offset in (-shift, 0, shift)]
    if not scenarios[1] or any(hit is None for scenario in scenarios for hit in scenario):
        base["reason"] = "The contract's temperature rule could not be checked."
        return base
    intervals = [wilson_interval(sum(scenario), len(scenario)) for scenario in scenarios]
    low = min(interval[0] for interval in intervals)
    high = max(interval[1] for interval in intervals)
    base.update(yes_probability=round(sum(scenarios[1]) / len(scenarios[1]), 3),
                yes_range_low=round(low, 3), yes_range_high=round(high, 3),
                model_shift_c=round(shift, 2))
    fee_rate = market_fee_rate(market)
    if fee_rate is None:
        base["reason"] = "The market's current trading fee could not be confirmed."
        return base
    options = []
    for side in ("YES", "NO"):
        token = next((t for t in tokens if t["market_id"] == market["id"] and t["outcome"] == side), None)
        if not token:
            continue
        snapshot = latest_snapshot(snapshots, token["token_id"])
        quote = ask_quote(snapshot)
        if not quote:
            continue
        quote_age = (now - datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))).total_seconds()
        if not -60 <= quote_age <= 15 * 60:
            continue
        ask, size = quote
        if not 0.01 <= ask <= 0.99 or size < MIN_BOOK_SHARES or ask * size < MIN_BOOK_DOLLARS:
            continue
        fee = round(fee_rate * ask * (1 - ask), 5)
        conservative_probability = low if side == "YES" else 1 - high
        edge = conservative_probability - ask - fee
        options.append((edge, side, ask, fee, size))
    if not options:
        base["reason"] = "No fresh YES or NO ask has enough shares at its best price."
        return base
    edge, side, ask, fee, size = max(options)
    base.update(best_side=side, best_ask=ask, fee_per_share=fee,
                conservative_edge=round(edge, 3), quote_size=round(size, 2))
    if edge < MIN_EDGE:
        base["reason"] = "Neither side is cheap enough after fees and uncertainty."
    else:
        base["signal"] = f"BUY {side}"
        base["reason"] = (f"The model's cautious {side} chance exceeds the live ask plus the "
                          f"taker fee by {edge * 100:.1f} percentage points.")
    return base
