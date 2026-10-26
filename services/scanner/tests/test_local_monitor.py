from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from threading import Event

from polyedge.config import Settings
from polyedge.database.local import LocalRepository
from polyedge.jobs import run_local as watcher


def test_closed_time_stops_local_snapshot_collection(tmp_path):
    repo = LocalRepository(tmp_path / "polyedge.json")
    market_id, _ = repo.upsert_market({
        "polymarket_market_id": "123",
        "market_status": "active",
        "market_type": "daily_max_temperature",
        "resolution_status": "needs_review",
        "end_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    })
    repo.upsert_token(market_id, "456", "YES", "token")
    repo.start_run("snapshots")
    assert repo.data["markets"][0]["market_status"] == "suspended"
    assert repo.active_tokens() == []
    assert LocalRepository(repo.path).data["markets"][0]["market_status"] == "suspended"


def test_watcher_runs_discovery_then_price_refresh(monkeypatch):
    stop = Event()
    modes = []
    forecast_runs = []
    observation_runs = []

    def fake_scan(_settings, *, mode):
        modes.append(mode)
        if len(modes) == 2:
            stop.set()
        return {"markets_discovered": 0, "markets_updated": 0,
                "snapshots_created": 0, "errors_count": 0}

    monkeypatch.setattr(watcher, "scan", fake_scan)
    monkeypatch.setattr(watcher, "collect_forecasts", lambda _settings: forecast_runs.append(1) or {"forecasts_created": 0, "errors_count": 0})
    monkeypatch.setattr(watcher, "collect_observations", lambda _settings: observation_runs.append(1) or {"observations_created": 0, "errors_count": 0})
    monkeypatch.setattr(watcher, "scanner_lock", nullcontext)
    watcher.run_local(Settings(), stop, discovery_seconds=1, snapshot_seconds=0.001)
    assert modes == ["all", "snapshots"]
    assert forecast_runs == [1]
    assert observation_runs == [1]
