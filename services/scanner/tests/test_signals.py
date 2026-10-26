from datetime import datetime, timedelta, timezone

from polyedge.weather.signals import (ask_quote, contract_hit, decide, station_validation,
                                      wilson_interval)


def test_contract_rule_rounding_and_bounds():
    market = {"resolution_rules": "measures temperatures to whole degrees Celsius",
              "temperature_unit": "C", "comparison_operator": "eq", "threshold": "21"}
    assert contract_hit(20.5, market) is True
    assert contract_hit(21.5, market) is False
    market["comparison_operator"] = "lte"
    assert contract_hit(20.5, market) is True
    market["temperature_unit"] = "F"
    market["threshold"] = "70"
    assert contract_hit(21.1, market) is True


def test_station_validation_uses_only_complete_local_days_and_rolling_holdout():
    history, observations = [], []
    for offset in range(28):
        day = datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=offset)
        history.append({"target_date": day.date().isoformat(), "forecast_high_c": 20,
                        "hourly_count": 24})
        for hour in range(24):
            observations.append({"observed_at": (day + timedelta(hours=hour)).isoformat(),
                                 "temp_c": 21 if hour == 15 else 15})
    stats = station_validation(history, observations, "UTC")
    assert stats["history_days"] == 28
    assert stats["holdout_days"] == 7
    assert stats["holdout_mae_c"] == 0
    assert stats["median_bias_c"] == 1


def test_best_ask_uses_price_level_and_fee_before_buy():
    now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
    market = {"id": "m", "station_id": "TEST", "target_date": "2026-10-13",
              "resolution_rules": "whole degrees Celsius", "temperature_unit": "C",
              "comparison_operator": "gte", "threshold": "21",
              "raw_metadata": {"feesEnabled": True, "feeType": "weather_fees",
                               "feeSchedule": {"exponent": 1, "rate": 0.05, "takerOnly": True}}}
    forecast = {"collected_at": now.isoformat(), "members_c": [20] * 30, "grid_distance_km": 2}
    validation = {"history_days": 28, "training_days": 21, "holdout_days": 7,
                  "holdout_mae_c": 1, "holdout_80pct_coverage": 0.8,
                  "median_bias_c": 3, "residuals_c": [3] * 28}
    tokens = [{"market_id": "m", "token_id": "yes", "outcome": "YES"},
              {"market_id": "m", "token_id": "no", "outcome": "NO"}]
    snapshots = [{"token_id": "yes", "captured_at": now.isoformat(), "best_ask": "0.50",
                  "raw_orderbook": {"asks": [{"price": "0.70", "size": "100"},
                                            {"price": "0.50", "size": "20"}]}},
                 {"token_id": "no", "captured_at": now.isoformat(), "best_ask": "0.80",
                  "raw_orderbook": {"asks": [{"price": "0.80", "size": "100"}]}}]
    assert ask_quote(snapshots[0]) == (0.5, 20)
    result = decide(market, forecast, validation, tokens, snapshots, now)
    assert result["signal"] == "BUY YES"
    assert result["fee_per_share"] == 0.0125
    assert result["conservative_edge"] > 0.3
    snapshots[0]["captured_at"] = (now - timedelta(minutes=20)).isoformat()
    assert decide(market, forecast, validation, tokens, snapshots, now)["signal"] == "NO BUY"


def test_wilson_interval_keeps_small_samples_uncertain():
    low, high = wilson_interval(10, 10)
    assert 0.7 < low < 0.8
    assert high == 1
