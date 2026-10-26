from datetime import datetime, timezone
from typing import Any

from polyedge.polymarket.schemas import OrderBook


def normalize_book(raw: dict[str, Any], asset_id: str, market_id: str) -> dict[str, Any]:
    book = OrderBook.model_validate(raw)
    if book.asset_id != asset_id:
        raise ValueError("CLOB asset ID mismatch")
    bid = max(book.bids, key=lambda level: level.price, default=None)
    ask = min(book.asks, key=lambda level: level.price, default=None)
    if bid and ask and bid.price > ask.price:
        raise ValueError("crossed order book")
    return {
        "market_id": market_id, "token_id": asset_id,
        "best_bid": str(bid.price) if bid else None,
        "best_ask": str(ask.price) if ask else None,
        "spread": str(ask.price - bid.price) if ask and bid else None,
        "bid_liquidity": str(sum((level.size for level in book.bids), start=0)) if book.bids else None,
        "ask_liquidity": str(sum((level.size for level in book.asks), start=0)) if book.asks else None,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "api_timestamp": book.captured_at_api(), "raw_orderbook": raw,
    }
