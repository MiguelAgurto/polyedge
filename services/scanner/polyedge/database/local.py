"""Local, atomic JSON storage shared with the Next.js dashboard."""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalRepository:
    SNAPSHOTS_PER_TOKEN = 48

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, list[dict[str, Any]]] = {
            "markets": [], "tokens": [], "snapshots": [], "runs": [], "errors": [],
            "forecasts": [], "ensemble_votes": [],
            "observations": [],
            "historical_forecasts": [], "signals": [], "trader_research": [],
        }
        if path.exists():
            loaded = json.loads(path.read_text())
            for key in self.data:
                self.data[key] = loaded.get(key, [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".polyedge-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.data, handle, ensure_ascii=False, separators=(",", ":"), default=str)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def start_run(self, mode: str) -> str:
        self.expire_markets()
        run_id = str(uuid.uuid4())
        self.data["runs"].insert(0, {
            "id": run_id, "started_at": utcnow(), "completed_at": None,
            "mode": mode, "status": "running", "markets_discovered": 0,
            "markets_updated": 0, "snapshots_created": 0, "errors_count": 0,
        })
        self.data["runs"] = self.data["runs"][:100]
        self.save()
        return run_id

    def finish_run(self, run_id: str, **stats: Any) -> None:
        for run in self.data["runs"]:
            if run["id"] == run_id:
                run.update(stats)
                run["completed_at"] = utcnow()
                break
        self.save()

    def error(self, run_id: str, error_type: str, message: str, market_id: str | None = None) -> None:
        self.data["errors"].insert(0, {
            "id": uuid.uuid4().int,
            "scanner_run_id": run_id, "market_id": market_id,
            "error_type": error_type, "error_message": message[:2000],
            "created_at": utcnow(),
        })
        self.data["errors"] = self.data["errors"][:100]

    def upsert_market(self, row: dict[str, Any]) -> tuple[str, bool]:
        for market in self.data["markets"]:
            if market["polymarket_market_id"] == row["polymarket_market_id"]:
                review = market.get("resolution_status")
                market.update(row)
                if review != "needs_review":
                    market["resolution_status"] = review
                market["updated_at"] = utcnow()
                return market["id"], False
        market_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"polyedge:market:{row['polymarket_market_id']}"))
        now = utcnow()
        self.data["markets"].append({**row, "id": market_id, "created_at": now, "updated_at": now})
        return market_id, True

    def upsert_token(self, market_id: str, token_id: str, outcome: str, asset_kind: str) -> None:
        for token in self.data["tokens"]:
            if token["market_id"] == market_id and token["outcome"] == outcome:
                token.update(token_id=token_id, asset_kind=asset_kind)
                return
        self.data["tokens"].append({
            "id": str(uuid.uuid4()), "market_id": market_id,
            "token_id": token_id, "outcome": outcome, "asset_kind": asset_kind,
        })

    def snapshot(self, row: dict[str, Any]) -> None:
        self.data["snapshots"].append({**row, "id": uuid.uuid4().int})
        token_rows = [s for s in self.data["snapshots"] if s["token_id"] == row["token_id"]]
        if len(token_rows) > self.SNAPSHOTS_PER_TOKEN:
            oldest_ids = {s["id"] for s in token_rows[:-self.SNAPSHOTS_PER_TOKEN]}
            self.data["snapshots"] = [s for s in self.data["snapshots"] if s["id"] not in oldest_ids]

    def expire_markets(self) -> None:
        now = datetime.now(timezone.utc)
        for market in self.data["markets"]:
            if market["market_status"] != "active" or not market.get("end_at"):
                continue
            try:
                end_at = datetime.fromisoformat(market["end_at"].replace("Z", "+00:00"))
            except ValueError:
                continue
            if end_at.tzinfo is None:
                end_at = end_at.replace(tzinfo=timezone.utc)
            if end_at.astimezone(timezone.utc) <= now:
                market["market_status"] = "suspended"
                market["updated_at"] = now.isoformat()

    def active_tokens(self) -> list[dict[str, Any]]:
        self.expire_markets()
        active_ids = {
            m["id"] for m in self.data["markets"]
            if m["market_status"] == "active" and m["market_type"] == "daily_max_temperature"
        }
        return [t for t in self.data["tokens"] if t["market_id"] in active_ids]

    def add_forecast(self, row: dict[str, Any]) -> str:
        forecast_id = str(uuid.uuid4())
        self.data["forecasts"].append({**row, "id": forecast_id})
        # Keep the most recent 90 days of forecast runs for later validation.
        cutoff = datetime.now(timezone.utc).timestamp() - 90 * 86400
        self.data["forecasts"] = [
            item for item in self.data["forecasts"]
            if datetime.fromisoformat(item["collected_at"].replace("Z", "+00:00")).timestamp() >= cutoff
        ]
        retained_ids = {item["id"] for item in self.data["forecasts"]}
        self.data["ensemble_votes"] = [
            item for item in self.data["ensemble_votes"] if item["forecast_id"] in retained_ids
        ]
        return forecast_id

    def upsert_ensemble_vote(self, row: dict[str, Any]) -> None:
        self.data["ensemble_votes"] = [
            item for item in self.data["ensemble_votes"] if item["market_id"] != row["market_id"]
        ]
        self.data["ensemble_votes"].append(row)

    def add_observations(self, rows: list[dict[str, Any]]) -> int:
        known = {item["id"] for item in self.data["observations"]}
        created = 0
        for row in rows:
            observation_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"polyedge:observation:{row['station_id']}:{row['observed_at']}:{row['raw_ob']}",
            ))
            if observation_id not in known:
                self.data["observations"].append({**row, "id": observation_id})
                known.add(observation_id)
                created += 1
        cutoff = datetime.now(timezone.utc).timestamp() - 30 * 86400
        self.data["observations"] = [
            item for item in self.data["observations"]
            if datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")).timestamp() >= cutoff
        ]
        return created

    def upsert_historical_forecast(self, row: dict[str, Any]) -> None:
        self.data["historical_forecasts"] = [
            item for item in self.data["historical_forecasts"]
            if not (item["station_id"] == row["station_id"] and
                    item["target_date"] == row["target_date"] and
                    item["model"] == row["model"] and
                    item["lead_days"] == row["lead_days"])
        ]
        self.data["historical_forecasts"].append(row)

    def replace_signals(self, rows: list[dict[str, Any]]) -> None:
        self.data["signals"] = rows
        self.save()
