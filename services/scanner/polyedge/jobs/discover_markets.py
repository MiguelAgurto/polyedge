"""Read-only Polymarket scanner. Run with python -m polyedge.jobs.discover_markets."""
import argparse
import fcntl
import json
import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polyedge.config import Settings
from polyedge.database.client import get_client
from polyedge.database.local import LocalRepository
from polyedge.database.repository import Repository
from polyedge.polymarket.client import PolymarketClient
from polyedge.polymarket.orderbook import normalize_book
from polyedge.polymarket.schemas import extract_binary_assets
from polyedge.weather.classifier import classify
from polyedge.weather.parser import normalize_market

log = logging.getLogger("polyedge.scanner")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("market_id", "error_type", "path", "status", "attempt", "error"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


@contextmanager
def scanner_lock():
    path = Path("/tmp/polyedge-scanner.lock")
    with path.open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another scanner job is running") from exc
        yield


def scan(settings: Settings, *, mode: str = "all", dry_run: bool = False,
         client: PolymarketClient | None = None, repository: Repository | LocalRepository | None = None) -> dict[str, int]:
    if mode not in {"all", "discover", "snapshots"}:
        raise ValueError("invalid scan mode")
    if not dry_run and repository is None:
        repository = LocalRepository(settings.data_file) if settings.storage == "local" else Repository(get_client(settings))
    own_client = client is None
    client = client or PolymarketClient(settings)
    stats = {"markets_discovered": 0, "markets_updated": 0, "snapshots_created": 0, "errors_count": 0}
    run_id = repository.start_run(mode) if repository else None

    def record_error(exc: Exception, market_id: str | None = None) -> None:
        stats["errors_count"] += 1
        log.exception("scan_error", extra={"market_id": market_id, "error_type": type(exc).__name__})
        if repository and run_id:
            repository.error(run_id, type(exc).__name__, str(exc), market_id)

    def collect(token_id: str, market_id: str) -> None:
        try:
            row = normalize_book(client.order_book(token_id), token_id, market_id)
            if repository:
                repository.snapshot(row)
            else:
                print(json.dumps({"snapshot": {k: v for k, v in row.items() if k != "raw_orderbook"}}, default=str))
            stats["snapshots_created"] += 1
        except Exception as exc:
            record_error(exc, market_id)

    try:
        if mode in {"all", "discover"}:
            try:
                def candidates():
                    seen: set[str] = set()
                    recent_limit = max(1, settings.discovery_limit * 4 // 5)
                    try:
                        for item in client.recent_temperature_markets(recent_limit):
                            seen.add(item.id)
                            yield item
                    except Exception as exc:
                        record_error(exc)
                    try:
                        tag_id = client.weather_tag_id()
                    except Exception as exc:
                        record_error(exc)
                        tag_id = None
                    remaining = settings.discovery_limit - len(seen)
                    if remaining <= 0:
                        return
                    for item in client.active_markets(limit=remaining, tag_id=tag_id):
                        if item.id not in seen:
                            seen.add(item.id)
                            yield item

                for listing in candidates():
                    if classify(listing.question, listing.description) is None:
                        continue
                    try:
                        market = client.market(listing.id)
                        if not market.events and listing.events:
                            market.events = listing.events
                        event = None
                        if market.events and market.events[0].get("id") is not None:
                            try:
                                event = client.event(str(market.events[0]["id"]))
                            except Exception as exc:
                                record_error(exc, market.id)
                        row = normalize_market(market, event)
                        kind = None
                        assets = None
                        if row["market_type"] == "daily_max_temperature" and row["market_status"] == "active":
                            try:
                                kind, assets = extract_binary_assets(market)
                            except ValueError as exc:
                                record_error(exc, market.id)
                        if repository:
                            market_id, created = repository.upsert_market(row)
                            for outcome, asset_id in (assets or {}).items():
                                repository.upsert_token(market_id, asset_id, outcome, kind)
                        else:
                            market_id, created = market.id, True
                            print(json.dumps({"market": {k: v for k, v in row.items() if k not in {"raw_metadata", "description", "resolution_rules"}}, "asset_kind": kind, "assets": assets}, default=str))
                        stats["markets_discovered" if created else "markets_updated"] += 1
                        if mode == "all" and row["market_status"] == "active":
                            for asset_id in (assets or {}).values():
                                collect(asset_id, market_id)
                    except Exception as exc:
                        record_error(exc, listing.id)
            except Exception as exc:
                record_error(exc)
        if mode == "snapshots":
            if not repository:
                raise ValueError("snapshot-only dry run requires stored market tokens")
            for token in repository.active_tokens():
                collect(token["token_id"], token["market_id"])
    finally:
        if repository and run_id:
            repository.finish_run(run_id, status="partial" if stats["errors_count"] else "success", **stats)
        if own_client:
            client.http.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover public Polymarket weather markets and collect books")
    parser.add_argument("--dry-run", action="store_true", help="fetch public data and print JSON without database writes")
    parser.add_argument("--mode", choices=["all", "discover", "snapshots"], default="all")
    parser.add_argument("--storage", choices=["local", "supabase"], help="override POLYEDGE_STORAGE (default: local)")
    args = parser.parse_args(argv)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        with scanner_lock():
            settings = Settings()
            if args.storage:
                settings.storage = args.storage
            stats = scan(settings, mode=args.mode, dry_run=args.dry_run)
        print(json.dumps({"summary": stats}))
        return 0 if stats["errors_count"] == 0 else 1
    except Exception:
        log.exception("scanner_fatal")
        return 1


if __name__ == "__main__":
    sys.exit(main())
