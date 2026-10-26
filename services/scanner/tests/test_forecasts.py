from datetime import date, timedelta

import httpx

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.collect_forecasts import collect
from polyedge.jobs.collect_observations import collect as collect_observations
from polyedge.weather.ensemble import OpenMeteoClient, member_vote
from polyedge.weather.station import AviationWeatherClient


def test_live_shape_is_parsed_and_missing_members_are_excluded():
    def handler(request):
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [
                {"name": "Paris", "latitude": 33.6, "longitude": -95.5,
                 "timezone": "America/Chicago", "country": "United States", "population": 25000},
                {"name": "Paris", "latitude": 48.86, "longitude": 2.35,
                 "timezone": "Europe/Paris", "country": "France", "population": 2100000},
            ]})
        return httpx.Response(200, json={
            "latitude": 48.8, "longitude": 2.4, "timezone": "Europe/Paris",
            "daily": {"time": ["2026-10-13"], "temperature_2m_max": [19.5],
                      **{f"temperature_2m_max_member{i:02d}": [None if i == 10 else 19 + i / 10]
                         for i in range(1, 12)}},
        })
    client = OpenMeteoClient()
    client.http.close()
    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        location = client.geocode("Paris")
        grid, rows = client.daily_highs(location)
    finally:
        client.close()
    assert location["country"] == "France"
    assert grid["grid_latitude"] == 48.8
    assert rows[0]["target_date"] == "2026-10-13"
    assert len(rows[0]["members_c"]) == 10


def test_archived_hourly_forecast_requires_most_of_the_local_day():
    client = OpenMeteoClient()
    client.http.close()
    client.http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "latitude": 48.8, "longitude": 2.4,
        "hourly": {"time": [f"2026-09-20T{hour:02d}:00" for hour in range(24)] +
                           [f"2026-09-21T{hour:02d}:00" for hour in range(19)],
                   "temperature_2m_previous_day1": list(range(24)) + list(range(19))},
    })))
    try:
        grid, rows = client.historical_daily_highs(
            {"latitude": 48.9, "longitude": 2.4, "timezone": "Europe/Paris"},
            "2026-09-20", "2026-09-21")
    finally:
        client.close()
    assert grid["grid_latitude"] == 48.8
    assert rows == [{"target_date": "2026-09-20", "forecast_high_c": 23.0,
                     "hourly_count": 24}]


def test_member_vote_uses_whole_degree_contract_rule():
    assert member_vote([20.4, 20.5, 21.4], "21", "eq", "C", whole_degrees=True) == (2, 3)
    assert member_vote([20.4], "20", "gte", "C", whole_degrees=False) is None
    assert member_vote([0.0, 1.0], "32", "eq", "F", whole_degrees=True) == (1, 2)


def test_noaa_station_metadata_matches_explicit_id():
    client = AviationWeatherClient()
    client.http.close()
    client.http = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[
        {"icaoId": "LFPB", "site": "Paris/Le Bourget Arpt", "lat": 48.967,
         "lon": 2.428, "country": "FR"},
        {"icaoId": "XXXX", "site": "Other", "lat": 0, "lon": 0, "country": "ZZ"},
    ])))
    try:
        stations = client.station_info({"LFPB"})
    finally:
        client.close()
    assert list(stations) == ["LFPB"]
    assert stations["LFPB"]["latitude"] == 48.967


def test_noaa_metars_filter_wrong_station_and_missing_temperature():
    client = AviationWeatherClient()
    client.http.close()
    client.http = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[
        {"icaoId": "LFPB", "obsTime": 1791819000, "temp": 20,
         "rawOb": "METAR LFPB 121530Z ...", "metarType": "METAR"},
        {"icaoId": "LFPB", "obsTime": 1791817200, "temp": None},
        {"icaoId": "RKSI", "obsTime": 1791819000, "temp": 21},
    ])))
    try:
        rows = client.metars("LFPB")
    finally:
        client.close()
    assert len(rows) == 1
    assert rows[0]["station_id"] == "LFPB"
    assert rows[0]["temp_c"] == 20.0


def test_collection_keeps_forecasts_and_votes_across_reloads(tmp_path):
    target = (date.today() + timedelta(days=1)).isoformat()
    repo = LocalRepository(tmp_path / "polyedge.json")
    market_id, _ = repo.upsert_market({
        "polymarket_market_id": "1", "market_status": "active",
        "market_type": "daily_max_temperature", "resolution_status": "needs_review",
        "city": "Paris", "target_date": target, "threshold": "21",
        "comparison_operator": "eq", "temperature_unit": "C",
        "resolution_source": "https://www.weather.gov/wrh/timeseries?site=lfpb",
        "resolution_rules": "This source measures temperatures to whole degrees Celsius.",
    })
    repo.save()

    class FakeClient:
        MODEL = "gfs_seamless"

        def geocode(self, _city):
            return {"name": "Paris", "country": "France", "latitude": 48.86,
                    "longitude": 2.35, "timezone": "Europe/Paris", "country_code": "FR"}

        def daily_highs(self, _location):
            return ({"grid_latitude": 48.8, "grid_longitude": 2.4,
                     "grid_timezone": "Europe/Paris"},
                    [{"target_date": target, "members_c": [20.6] * 30}])

    settings = Settings(data_file=repo.path, storage="local")
    class FakeStationClient:
        def station_info(self, _ids):
            return {"LFPB": {"station_id": "LFPB", "station_name": "Paris/Le Bourget Arpt",
                             "latitude": 48.967, "longitude": 2.428, "country_code": "FR"}}

    assert collect(settings, FakeClient(), FakeStationClient())["votes_updated"] == 1
    assert collect(settings, FakeClient(), FakeStationClient())["votes_updated"] == 1
    stored = LocalRepository(repo.path).data
    assert len(stored["forecasts"]) == 2  # archive both runs
    assert len(stored["ensemble_votes"]) == 1  # latest vote per market
    assert stored["ensemble_votes"][0]["market_id"] == market_id
    assert stored["ensemble_votes"][0]["yes_members"] == 30
    assert stored["forecasts"][-1]["station_id"] == "LFPB"
    assert stored["markets"][0]["station_id"] == "LFPB"


def test_observation_collection_deduplicates_hourly_refresh(tmp_path):
    from datetime import datetime, timezone
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    repo = LocalRepository(tmp_path / "polyedge.json")
    repo.upsert_market({
        "polymarket_market_id": "1", "market_status": "active",
        "market_type": "daily_max_temperature", "resolution_status": "needs_review",
        "station_id": "LFPB", "target_date": date.today().isoformat(),
    })
    repo.save()

    class FakeClient:
        def metars(self, _station_id, hours):
            assert hours == 24
            return [{"station_id": "LFPB", "observed_at": observed_at,
                     "temp_c": 20.0, "raw_ob": "METAR LFPB test", "report_type": "METAR",
                     "source": "NOAA Aviation Weather METAR"}]

    settings = Settings(data_file=repo.path, storage="local")
    assert collect_observations(settings, FakeClient(), pause_seconds=0)["observations_created"] == 1
    assert collect_observations(settings, FakeClient(), pause_seconds=0)["observations_created"] == 0
    assert len(LocalRepository(repo.path).data["observations"]) == 1
