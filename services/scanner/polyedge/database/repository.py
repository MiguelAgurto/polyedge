from typing import Any

from supabase import Client


class Repository:
    def __init__(self, client: Client):
        self.client = client

    def start_run(self, mode: str) -> str:
        row = self.client.table("scanner_runs").insert({"status": "running", "mode": mode}).execute().data[0]
        return row["id"]

    def finish_run(self, run_id: str, **stats: Any) -> None:
        from datetime import datetime, timezone
        self.client.table("scanner_runs").update({"completed_at": datetime.now(timezone.utc).isoformat(), **stats}).eq("id", run_id).execute()

    def error(self, run_id: str, error_type: str, message: str, market_id: str | None = None) -> None:
        self.client.table("scanner_errors").insert({"scanner_run_id": run_id, "market_id": market_id, "error_type": error_type, "error_message": message[:2000]}).execute()

    def upsert_market(self, row: dict[str, Any]) -> tuple[str, bool]:
        existing = self.client.table("markets").select("id,resolution_status").eq("polymarket_market_id", row["polymarket_market_id"]).limit(1).execute().data
        if existing:
            # Preserve a human verification decision on refresh.
            if existing[0]["resolution_status"] != "needs_review":
                row = {**row, "resolution_status": existing[0]["resolution_status"]}
            self.client.table("markets").update(row).eq("id", existing[0]["id"]).execute()
            return existing[0]["id"], False
        result = self.client.table("markets").upsert(row, on_conflict="polymarket_market_id").execute().data[0]
        return result["id"], True

    def upsert_token(self, market_id: str, token_id: str, outcome: str, asset_kind: str) -> None:
        self.client.table("market_tokens").upsert({"market_id": market_id, "token_id": token_id, "outcome": outcome, "asset_kind": asset_kind}, on_conflict="market_id,outcome").execute()

    def snapshot(self, row: dict[str, Any]) -> None:
        self.client.table("market_snapshots").insert(row).execute()

    def active_tokens(self) -> list[dict[str, Any]]:
        # Paginate PostgREST's default 1000-row cap.
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            batch = self.client.table("market_tokens").select("token_id,outcome,market_id,markets!inner(market_status,market_type)").eq("markets.market_status", "active").eq("markets.market_type", "daily_max_temperature").range(offset, offset + 499).execute().data
            rows.extend(batch)
            if len(batch) < 500:
                return rows
            offset += 500
