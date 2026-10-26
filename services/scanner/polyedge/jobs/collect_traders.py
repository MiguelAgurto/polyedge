"""Save a small, read-only watchlist from Polymarket's public Data API v2."""

from datetime import datetime, timezone
from typing import Any

import httpx

from polyedge.config import Settings
from polyedge.database.local import LocalRepository, utcnow


BASE_URL = "https://data-api.polymarket.com"
WATCHLIST = (
    ("TunSahur", "0x95d381e71dba6f1c3199fd9bc040383d6fae6eff", "Paper-copy candidate"),
    ("badatmath.", "0x8fbd7cf5f806f563080864694415829f7229a959", "Strategy study"),
    ("HighTempTation", "0x6011655c4afb76f36dd1b08a137a1ba73466b31e", "Timing study"),
    ("OutOfMemory", "0x5bae7577f470244ce8e678d20693eee2b8ffed25", "Emerging trader"),
    ("WrongBy1Degree", "0x0a0c42f6b1da5a633ec1a4d45ba76eb486c1a853", "Secondary watch"),
    ("Bilberry", "0xbf13934a1fec7d3211fc15c138d84ac2a691b91a", "Secondary watch"),
)


def _rows(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("unexpected Polymarket Data API response")
    return [row for row in data if isinstance(row, dict)]


def _get(client: httpx.Client, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.get(path, params=params)
    response.raise_for_status()
    return _rows(response.json())


def _time(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _fill(row: dict[str, Any]) -> dict[str, Any]:
    slug = row.get("event_slug") or row.get("slug")
    return {
        "timestamp": _time(row.get("timestamp")),
        "side": row.get("side"),
        "title": row.get("title") or "Untitled market",
        "outcome": row.get("outcome"),
        "price": _number(row.get("price")),
        "size": _number(row.get("size")),
        "condition_id": row.get("condition_id"),
        "token_id": row.get("token_id"),
        "market_url": f"https://polymarket.com/event/{slug}" if slug else None,
    }


def _is_temperature(row: dict[str, Any]) -> bool:
    title = str(row.get("title") or "").lower()
    return "highest temperature" in title or "high temperature" in title


def collect(settings: Settings, client: httpx.Client | None = None) -> dict[str, int]:
    if settings.storage != "local":
        raise ValueError("Trader research currently requires local storage")
    repo = LocalRepository(settings.data_file)
    previous = {row["wallet"].lower(): row for row in repo.data["trader_research"]}
    checked_at = utcnow()
    errors = 0
    updated = 0
    owned_client = client is None
    if client is None:
        client = httpx.Client(base_url=BASE_URL, timeout=settings.request_timeout,
                              headers={"User-Agent": "PolyEdge local research"})
    try:
        boards: dict[str, dict[str, dict[str, Any]]] = {}
        board_errors: list[str] = []
        for period in ("all", "month", "week"):
            try:
                rows = _get(client, "/v2/leaderboard", {
                    "time_period": period, "category": "weather", "sort_by": "PNL", "limit": 100,
                })
                boards[period] = {str(row.get("user_id") or "").lower(): row for row in rows}
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                board_errors.append(f"{period} leaderboard: {exc}")
                errors += 1

        result = []
        for name, wallet, role in WATCHLIST:
            old = previous.get(wallet, {})
            row = {**old, "name": name, "wallet": wallet, "role": role,
                   "profile_url": f"https://polymarket.com/profile/{wallet}",
                   "checked_at": checked_at, "last_error": None}
            rank = dict(old.get("rank") or {})
            pnl = dict(old.get("pnl") or {})
            for period, board in boards.items():
                entry = board.get(wallet)
                rank[period] = int(entry["rank"]) if entry and entry.get("rank") is not None else None
                pnl[period] = _number(entry.get("pnl")) if entry else None
            row["rank"] = rank
            row["pnl"] = pnl
            if boards:
                row["rank_updated_at"] = checked_at
            try:
                fills = _get(client, "/v2/trades", {
                    "user": wallet, "limit": 100, "taker_only": "false",
                })
                # The public endpoint includes all categories. This tab tracks
                # daily high temperature activity relevant to PolyEdge.
                temperature = [fill for fill in fills if _is_temperature(fill)]
                row.update({
                    "recent_fills": [_fill(fill) for fill in temperature[:12]],
                    "sample_fills": len(fills),
                    "sample_temperature_fills": len(temperature),
                    "sample_buy_fills": sum(str(fill.get("side")).upper() == "BUY" for fill in temperature),
                    "sample_markets": len({fill.get("condition_id") for fill in temperature if fill.get("condition_id")}),
                    "last_trade_at": _time(fills[0].get("timestamp")) if fills else None,
                    "updated_at": checked_at,
                })
                updated += 1
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                row["last_error"] = f"Recent trades: {exc}"
                errors += 1
            if board_errors:
                row["last_error"] = "; ".join(filter(None, [row["last_error"], *board_errors]))[:500]
            result.append(row)
        repo.data["trader_research"] = result
        repo.save()
    finally:
        if owned_client:
            client.close()
    return {"watched": len(WATCHLIST), "updated": updated, "errors_count": errors}
