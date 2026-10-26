import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GammaMarket(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    question: str = ""
    description: str | None = None
    resolutionSource: str | None = None
    slug: str | None = None
    version: str | None = None
    conditionId: str | None = None
    clobTokenIds: str | list[str] | None = None
    positionIds: str | list[str] | None = None
    outcomes: str | list[str] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    active: bool | None = None
    closed: bool | None = None
    acceptingOrders: bool | None = None
    enableOrderBook: bool | None = None
    endDate: str | None = None
    endDateIso: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError("market ID missing")
        return str(value)

    def raw(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)


def array_field(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON array") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("expected string array")
    return value


def extract_binary_assets(market: GammaMarket) -> tuple[str, dict[str, str]]:
    labels = array_field(market.outcomes)
    ids = array_field(market.positionIds if market.version == "v2" else market.clobTokenIds)
    if len(labels) != 2 or {label.casefold() for label in labels} != {"yes", "no"}:
        raise ValueError("not a verified YES/NO outcome mapping")
    if len(ids) != 2 or len(set(ids)) != 2 or any(not item.isdecimal() for item in ids):
        raise ValueError("invalid or missing outcome asset IDs")
    kind = "position" if market.version == "v2" else "token"
    return kind, {label.upper(): ids[index] for index, label in enumerate(labels)}


class OrderLevel(BaseModel):
    price: Decimal
    size: Decimal

    @field_validator("price")
    @classmethod
    def price_range(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or value >= 1:
            raise ValueError("price outside (0,1)")
        return value

    @field_validator("size")
    @classmethod
    def size_range(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("invalid size")
        return value


class OrderBook(BaseModel):
    model_config = ConfigDict(extra="allow")
    asset_id: str
    timestamp: str | int | None = None
    bids: list[OrderLevel]
    asks: list[OrderLevel]

    def captured_at_api(self) -> str | None:
        if self.timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(int(self.timestamp) / 1000, tz=timezone.utc).isoformat()
        except (ValueError, OverflowError):
            return None
