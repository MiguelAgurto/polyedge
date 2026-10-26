import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse

from polyedge.polymarket.schemas import GammaMarket
from polyedge.weather.classifier import classify

MONTHS = r"January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})\b", re.I)
CITY = re.compile(r"\btemperature\s+(?:in|for)\s+([A-Z][A-Za-z .()'-]{1,50}?)\s+(?:be|on|reach|exceed|above|below|over|under)\b")
TEMP = re.compile(r"(-?\d+(?:\.\d+)?)\s*°?\s*(F|C|Fahrenheit|Celsius)\b", re.I)


def station_id_from_source(source: str | None) -> str | None:
    """Read an explicit ICAO code only from NOAA's named resolution URL."""
    if not source:
        return None
    parsed = urlparse(source)
    if parsed.scheme != "https" or parsed.hostname not in {"weather.gov", "www.weather.gov"}:
        return None
    if parsed.path.lower() != "/wrh/timeseries":
        return None
    ids = parse_qs(parsed.query).get("site", [])
    if len(ids) != 1 or not re.fullmatch(r"[A-Za-z]{4}", ids[0]):
        return None
    return ids[0].upper()


def normalize_market(market: GammaMarket, event: dict[str, Any] | None = None) -> dict[str, Any]:
    question = market.question or ""
    category = classify(question, market.description)
    if category is None:
        raise ValueError("not a weather market")
    date_match = DATE.search(question)
    if not date_match:
        date_match = DATE.search((event.get("slug", "") if event else market.slug or "").replace("-", " "))
    target_date = None
    if date_match:
        try:
            target_date = datetime.strptime(" ".join(date_match.groups()), "%B %d %Y").date().isoformat()
        except ValueError:
            pass
    city_match = CITY.search(question)
    temp_match = TEMP.search(question)
    if re.search(r"\bbetween\b|\b-?\d+\s*[-–]\s*-?\d+\s*°?\s*[FC]\b", question, re.I):
        temp_match = None
    operator = None
    if re.search(r"\b(or higher|or above|at least)\b", question, re.I):
        operator = "gte"
    elif re.search(r"\b(or lower|or below|at most)\b", question, re.I):
        operator = "lte"
    elif re.search(r"\b(exceed|above|over|higher than)\b", question, re.I):
        operator = "gt"
    elif re.search(r"\b(below|under|less than)\b", question, re.I):
        operator = "lt"
    elif temp_match:
        operator = "eq"
    if temp_match is None:
        operator = None
    event_id = None
    if market.events and market.events[0].get("id") is not None:
        event_id = str(market.events[0]["id"])
    end_at = market.endDate or (market.endDateIso if market.endDateIso and "T" in market.endDateIso else None)
    if end_at:
        try:
            end_at = datetime.fromisoformat(end_at.replace("Z", "+00:00")).isoformat()
        except ValueError:
            end_at = None
    expired = bool(end_at and datetime.fromisoformat(end_at).astimezone(timezone.utc) <= datetime.now(timezone.utc))
    raw = market.raw()
    if event is not None:
        raw["_fetched_event"] = event
    return {
        "polymarket_market_id": market.id,
        "condition_id": market.conditionId or None,
        "event_id": event_id,
        "question": question,
        "description": market.description,
        "market_url": f"https://polymarket.com/event/{event['slug']}" if event and event.get("slug") else (f"https://polymarket.com/market/{market.slug}" if market.slug else None),
        "market_type": category,
        "city": city_match.group(1).strip() if city_match else None,
        "country": None,
        "station_id": station_id_from_source(market.resolutionSource),
        "target_date": target_date,
        "timezone": None,
        "threshold": str(Decimal(temp_match.group(1))) if temp_match else None,
        "temperature_unit": ("F" if temp_match.group(2).lower().startswith("f") else "C") if temp_match else None,
        "comparison_operator": operator,
        "resolution_source": market.resolutionSource or None,
        "resolution_rules": market.description if market.description and re.search(r"\b(resolv(?:e|es|ed|ing)|resolution)\b", market.description, re.I) else None,
        "resolution_status": "needs_review",
        "market_status": "closed" if market.closed else ("suspended" if expired or market.active is False or market.acceptingOrders is False or market.enableOrderBook is False else "active"),
        "end_at": end_at,
        "raw_metadata": raw,
    }
