import json
from polyedge.config import Settings
from polyedge.jobs.discover_markets import scan
from polyedge.database.local import LocalRepository
from polyedge.polymarket.schemas import GammaMarket


class FakeClient:
    def __init__(self, market, book, fail_book=False):
        self.m=GammaMarket.model_validate(market);self.book=book;self.fail_book=fail_book
    def weather_tag_id(self): return "84"
    def recent_temperature_markets(self, limit): return iter([])
    def active_markets(self, limit=None, tag_id=None): return iter([self.m])
    def market(self, _): return self.m
    def event(self, _): return {"id":"90177","slug":"london-weather"}
    def order_book(self, token):
        if self.fail_book: raise TimeoutError("CLOB timeout")
        return {**self.book,"asset_id":token}


class FakeRepository:
    def __init__(self): self.markets={};self.tokens={};self.books=[];self.runs=[];self.errors=[]
    def start_run(self,mode): self.runs.append({"mode":mode});return "run-id"
    def finish_run(self,run_id,**stats): self.runs[-1].update(stats)
    def error(self,run_id,kind,message,market_id=None):self.errors.append((kind,message,market_id))
    def upsert_market(self,row):
        new=row["polymarket_market_id"] not in self.markets
        self.markets[row["polymarket_market_id"]]=row
        return "db-id",new
    def upsert_token(self,market_id,token_id,outcome,asset_kind):self.tokens[outcome]=token_id
    def snapshot(self,row):self.books.append(row)
    def active_tokens(self):return [{"token_id":v,"market_id":"db-id"} for v in self.tokens.values()]


def test_dry_run_has_no_database_dependency(market_data,book_data,capsys):
    result=scan(Settings(),dry_run=True,client=FakeClient(market_data,book_data))
    assert result=={"markets_discovered":1,"markets_updated":0,"snapshots_created":2,"errors_count":0}
    output=capsys.readouterr().out.splitlines()
    assert "market" in json.loads(output[0]) and len(output)==3


def test_repeated_scan_updates_market(market_data,book_data):
    repo=FakeRepository();client=FakeClient(market_data,book_data)
    first=scan(Settings(),client=client,repository=repo)
    second=scan(Settings(),client=client,repository=repo)
    assert first["markets_discovered"]==1 and second["markets_updated"]==1
    assert len(repo.markets)==1 and len(repo.tokens)==2 and len(repo.books)==4


def test_one_book_failure_does_not_abort_scan(market_data,book_data):
    repo=FakeRepository()
    result=scan(Settings(),client=FakeClient(market_data,book_data,fail_book=True),repository=repo)
    assert result["markets_discovered"]==1 and result["errors_count"]==2
    assert repo.runs[0]["status"]=="partial" and len(repo.errors)==2


def test_local_scan_persists_for_dashboard(market_data,book_data,tmp_path):
    path=tmp_path / "polyedge.json"
    settings=Settings(data_file=path)
    first=scan(settings,client=FakeClient(market_data,book_data))
    stored=LocalRepository(path)
    assert first["snapshots_created"]==2
    assert len(stored.data["markets"])==1
    assert len(stored.data["tokens"])==2
    assert len(stored.data["snapshots"])==2
    assert stored.data["runs"][0]["status"]=="success"
    market_id=stored.data["markets"][0]["id"]
    second=scan(settings,client=FakeClient(market_data,book_data))
    stored=LocalRepository(path)
    assert second["markets_updated"]==1
    assert stored.data["markets"][0]["id"]==market_id
    assert len(stored.data["snapshots"])==4
