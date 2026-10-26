import pytest
from polyedge.polymarket.schemas import GammaMarket, extract_binary_assets
from polyedge.weather.classifier import classify
from polyedge.weather.parser import normalize_market, station_id_from_source


def test_classification():
    assert classify("Highest temperature in London on October 18?") == "daily_max_temperature"
    assert classify("Will the temperature in New York exceed 80°F?") == "daily_max_temperature"
    assert classify("Will it rain in London?") == "unsupported"
    assert classify("How much rainfall in London?") == "unsupported"
    assert classify("Temperature in Chicago on October 20?") == "unsupported"
    assert classify("Will a candidate win?") is None


def test_station_id_only_comes_from_explicit_noaa_source():
    assert station_id_from_source("https://www.weather.gov/wrh/timeseries?site=rksi") == "RKSI"
    assert station_id_from_source("https://weather.gov/wrh/timeseries?site=NZWN") == "NZWN"
    assert station_id_from_source("https://example.org/wrh/timeseries?site=RKSI") is None
    assert station_id_from_source("https://www.weather.gov/wrh/timeseries?site=RKSI&site=RJTT") is None


def test_normalization_never_invents_resolution(market_data):
    row=normalize_market(GammaMarket.model_validate(market_data), {"id":"90177","slug":"london-weather"})
    assert row["market_type"] == "daily_max_temperature"
    assert row["city"] == "London"
    assert row["target_date"] == "2099-10-18"
    assert row["station_id"] is None and row["resolution_source"] == "https://example.org/weather-observations"
    assert row["resolution_rules"] == market_data["description"]
    assert row["resolution_status"] == "needs_review"
    assert row["market_url"] == "https://polymarket.com/event/london-weather"
    assert row["raw_metadata"]["id"] == "703257"


def test_event_slug_supplies_explicit_year(market_data):
    market_data["question"]="Will the highest temperature in Seoul (Incheon) be 20°C or below on October 12?"
    row=normalize_market(GammaMarket.model_validate(market_data), {"id":"99","slug":"highest-temperature-in-seoul-on-october-12-2026"})
    assert row["city"] == "Seoul (Incheon)"
    assert row["target_date"] == "2026-10-12"


def test_range_does_not_invent_single_threshold(market_data):
    market_data["question"]="Will the highest temperature in London be between 20-21°C on October 18?"
    row=normalize_market(GammaMarket.model_validate(market_data))
    assert row["threshold"] is None and row["comparison_operator"] is None


def test_token_mapping_validated(market_data):
    kind, assets = extract_binary_assets(GammaMarket.model_validate(market_data))
    assert kind == "token" and assets["YES"].startswith("1075")
    market_data["outcomes"]='["No","Yes"]'
    _, reverse=extract_binary_assets(GammaMarket.model_validate(market_data))
    assert reverse["NO"].startswith("1075")
    market_data["outcomes"]='["Yes","Maybe"]'
    with pytest.raises(ValueError): extract_binary_assets(GammaMarket.model_validate(market_data))


def test_v2_uses_position_ids(market_data):
    market_data.update(version="v2", positionIds=["123","456"], clobTokenIds=None)
    assert extract_binary_assets(GammaMarket.model_validate(market_data)) == ("position", {"YES":"123","NO":"456"})
