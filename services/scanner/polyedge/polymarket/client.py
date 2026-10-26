import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

from polyedge.config import Settings
from polyedge.polymarket.schemas import GammaMarket

log = logging.getLogger(__name__)


class PolymarketClient:
    """Only public Gamma/CLOB GET endpoints are exposed."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.http = httpx.Client(timeout=settings.request_timeout, transport=transport,
                                 headers={"User-Agent": "PolyEdge/0.1 read-only"})
        self._events: dict[str, dict[str, Any]] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.http.close()

    def _get(self, base: str, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self.http.get(f"{base}{path}", params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.settings.max_retries:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            delay = min(float(retry_after), 30) if retry_after else 0
                        except ValueError:
                            delay = 0
                        delay = max(delay, min(0.5 * 2**attempt + random.uniform(0, .2), 8))
                        log.warning("api_retry", extra={"path": path, "status": response.status_code, "attempt": attempt + 1})
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self.settings.max_retries:
                    raise
                log.warning("api_retry", extra={"path": path, "error": str(exc), "attempt": attempt + 1})
                time.sleep(min(0.5 * 2**attempt + random.uniform(0, .2), 8))
        raise RuntimeError("unreachable retry state")

    def weather_tag_id(self) -> str:
        tag = self._get(self.settings.gamma_url, "/tags/slug/weather")
        if not isinstance(tag, dict) or tag.get("slug") != "weather" or not str(tag.get("id", "")).isdecimal():
            raise ValueError("invalid Gamma weather tag")
        return str(tag["id"])

    def recent_temperature_markets(self, limit: int) -> Iterator[GammaMarket]:
        """Search recent daily-temperature events; validate each child market."""
        yielded = 0
        seen: set[str] = set()
        for page_number in range(1, 11):
            page = self._get(self.settings.gamma_url, "/public-search", {
                "q": "highest temperature", "limit_per_type": 20, "page": page_number,
            })
            if not isinstance(page, dict) or not isinstance(page.get("events"), list):
                raise ValueError("invalid Gamma search page")
            for event in page["events"]:
                if not isinstance(event, dict) or not isinstance(event.get("markets"), list):
                    continue
                if event.get("closed") is True:
                    continue
                for raw in event["markets"]:
                    if not isinstance(raw, dict) or raw.get("closed") is True or raw.get("active") is False or raw.get("acceptingOrders") is False:
                        continue
                    end_at = raw.get("endDate")
                    if isinstance(end_at, str):
                        try:
                            if datetime.fromisoformat(end_at.replace("Z", "+00:00")).astimezone(timezone.utc) <= datetime.now(timezone.utc):
                                continue
                        except ValueError:
                            pass
                    item = GammaMarket.model_validate({**raw, "events": raw.get("events") or [{"id": event.get("id")}]})
                    if item.id in seen:
                        continue
                    seen.add(item.id)
                    yield item
                    yielded += 1
                    if yielded >= limit:
                        return
            pagination = page.get("pagination")
            if not isinstance(pagination, dict) or pagination.get("hasMore") is not True:
                return

    def active_markets(self, limit: int | None = None, tag_id: str | None = None) -> Iterator[GammaMarket]:
        remaining = self.settings.discovery_limit if limit is None else limit
        cursor: str | None = None
        seen: set[str] = set()
        market_ids: set[str] = set()
        while remaining > 0:
            params: dict[str, Any] = {"closed": "false", "limit": min(remaining, self.settings.page_size)}
            if tag_id is not None:
                params["tag_id"] = tag_id
            if cursor:
                params["after_cursor"] = cursor
            page = self._get(self.settings.gamma_url, "/markets/keyset", params)
            if not isinstance(page, dict) or not isinstance(page.get("markets"), list):
                raise ValueError("invalid Gamma markets page")
            for raw in page["markets"]:
                market = GammaMarket.model_validate(raw)
                if market.closed is True or market.active is False:
                    continue
                if market.id in market_ids:
                    continue
                market_ids.add(market.id)
                yield market
                remaining -= 1
                if remaining == 0:
                    break
            next_cursor = page.get("next_cursor")
            if not page["markets"] or not next_cursor:
                return
            if not isinstance(next_cursor, str) or next_cursor in seen:
                raise ValueError("invalid or repeated Gamma cursor")
            seen.add(next_cursor)
            cursor = next_cursor

    def market(self, market_id: str) -> GammaMarket:
        return GammaMarket.model_validate(self._get(self.settings.gamma_url, f"/markets/{market_id}"))

    def event(self, event_id: str) -> dict[str, Any]:
        if event_id in self._events:
            return self._events[event_id]
        data = self._get(self.settings.gamma_url, f"/events/{event_id}")
        if not isinstance(data, dict):
            raise ValueError("invalid Gamma event")
        self._events[event_id] = data
        return data

    def order_book(self, asset_id: str) -> dict[str, Any]:
        data = self._get(self.settings.clob_url, "/book", {"token_id": asset_id})
        if not isinstance(data, dict):
            raise ValueError("invalid CLOB book")
        return data
