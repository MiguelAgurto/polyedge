import httpx

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs.collect_traders import WATCHLIST, collect


def test_trader_snapshot_only_keeps_temperature_fills(tmp_path):
    wallet = WATCHLIST[0][1]

    def respond(request):
        if request.url.path == "/v2/leaderboard":
            return httpx.Response(200, json={"data": [{
                "user_id": wallet, "rank": 7, "pnl": 120.5,
            }]})
        return httpx.Response(200, json={"data": [
            {"title": "Will the highest temperature in Paris be 20°C?",
             "side": "BUY", "outcome": "Yes", "price": 0.4, "size": 10,
             "timestamp": 1791822635, "token_id": "token-1", "condition_id": "condition-1",
             "event_slug": "paris-event"},
            {"title": "Will the election happen?", "side": "BUY", "timestamp": 1791822634},
        ]})

    client = httpx.Client(base_url="https://data-api.polymarket.com",
                          transport=httpx.MockTransport(respond))
    settings = Settings(storage="local", data_file=tmp_path / "polyedge.json")
    result = collect(settings, client)
    rows = LocalRepository(settings.data_file).data["trader_research"]
    assert result == {"watched": len(WATCHLIST), "updated": len(WATCHLIST), "errors_count": 0}
    assert rows[0]["rank"] == {"all": 7, "month": 7, "week": 7}
    assert rows[0]["sample_temperature_fills"] == 1
    assert rows[0]["recent_fills"][0]["market_url"] == "https://polymarket.com/event/paris-event"
    assert rows[0]["recent_fills"][0]["price"] == 0.4


def test_failed_trader_request_preserves_previous_snapshot(tmp_path):
    settings = Settings(storage="local", data_file=tmp_path / "polyedge.json")
    repo = LocalRepository(settings.data_file)
    repo.data["trader_research"] = [{
        "wallet": WATCHLIST[0][1], "name": WATCHLIST[0][0], "updated_at": "2026-10-12T12:00:00+00:00",
        "recent_fills": [{"title": "Prior fill"}], "rank": {"week": 9}, "pnl": {"week": 25},
    }]
    repo.save()

    def fail(request):
        return httpx.Response(503)

    client = httpx.Client(base_url="https://data-api.polymarket.com",
                          transport=httpx.MockTransport(fail))
    result = collect(settings, client)
    saved = LocalRepository(settings.data_file).data["trader_research"][0]
    assert result["errors_count"] == 3 + len(WATCHLIST)
    assert saved["recent_fills"] == [{"title": "Prior fill"}]
    assert saved["updated_at"] == "2026-10-12T12:00:00+00:00"
    assert saved["rank"]["week"] == 9
    assert saved["last_error"]
