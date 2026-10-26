import json
import httpx
import pytest
from polyedge.config import Settings
from polyedge.polymarket.client import PolymarketClient
from polyedge.polymarket.orderbook import normalize_book


def test_keyset_pagination(market_data):
    seen=[]
    def handler(request):
        seen.append(request.url.params.get("after_cursor"))
        if len(seen)==1: return httpx.Response(200,json={"markets":[market_data],"next_cursor":"page2"})
        return httpx.Response(200,json={"markets":[{**market_data,"id":"703258"}],"next_cursor":None})
    with PolymarketClient(Settings(page_size=1), httpx.MockTransport(handler)) as client:
        assert [m.id for m in client.active_markets(limit=2)] == ["703257","703258"]
    assert seen == [None,"page2"]


def test_search_pagination_selects_open_market(market_data):
    pages=[]
    def handler(request):
        pages.append(request.url.params.get("page"))
        if len(pages)==1:
            return httpx.Response(200,json={"events":[{"id":"1","closed":False,"markets":[{**market_data,"endDate":"2020-01-01T00:00:00Z"}]}],"pagination":{"hasMore":True}})
        return httpx.Response(200,json={"events":[{"id":"2","closed":False,"markets":[{**market_data,"events":[]}]}],"pagination":{"hasMore":False}})
    with PolymarketClient(Settings(),httpx.MockTransport(handler)) as client:
        found=list(client.recent_temperature_markets(1))
    assert pages == ["1","2"] and found[0].events == [{"id":"2"}]


def test_retry_rate_limit_and_timeout(monkeypatch):
    monkeypatch.setattr("polyedge.polymarket.client.time.sleep", lambda _:None)
    attempts=0
    def handler(request):
        nonlocal attempts
        attempts+=1
        if attempts==1: raise httpx.ReadTimeout("timed out")
        if attempts==2: return httpx.Response(429,headers={"Retry-After":"0"})
        return httpx.Response(200,json={"markets":[],"next_cursor":None})
    with PolymarketClient(Settings(max_retries=2),httpx.MockTransport(handler)) as client:
        assert list(client.active_markets()) == []
    assert attempts == 3


def test_invalid_page_and_timeout(monkeypatch):
    monkeypatch.setattr("polyedge.polymarket.client.time.sleep", lambda _:None)
    with PolymarketClient(Settings(max_retries=0),httpx.MockTransport(lambda _:httpx.Response(200,json={}))) as client:
        with pytest.raises(ValueError,match="Gamma"): list(client.active_markets())
    with PolymarketClient(Settings(max_retries=1),httpx.MockTransport(lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("timeout")))) as client:
        with pytest.raises(httpx.ReadTimeout): list(client.active_markets())


def test_book_empty_and_best_levels(book_data):
    asset=book_data["asset_id"]
    row=normalize_book(book_data,asset,"market-id")
    assert row["best_bid"]=="0.12" and row["best_ask"]=="0.25" and row["spread"]=="0.13"
    assert row["bid_liquidity"]=="20" and row["ask_liquidity"]=="15"
    book_data.update(bids=[],asks=[])
    row=normalize_book(book_data,asset,"market-id")
    assert row["best_bid"] is None and row["spread"] is None


def test_book_rejects_invalid_prices_and_asset(book_data):
    with pytest.raises(ValueError,match="mismatch"): normalize_book(book_data,"other","market")
    book_data["asks"][0]["price"]="1.3"
    with pytest.raises(Exception): normalize_book(book_data,book_data["asset_id"],"market")
