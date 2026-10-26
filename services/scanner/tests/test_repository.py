from types import SimpleNamespace

from polyedge.database.repository import Repository


class MarketsTable:
    def __init__(self):
        self.rows={};self.operation="";self.payload=None;self.match=None
    def select(self,*_):self.operation="select";return self
    def eq(self,key,value):self.match=(key,value);return self
    def limit(self,*_):return self
    def update(self,payload):self.operation="update";self.payload=payload;return self
    def upsert(self,payload,**_):self.operation="upsert";self.payload=payload;return self
    def execute(self):
        if self.operation=="select":
            row=self.rows.get(self.match[1]);return SimpleNamespace(data=[{"id":row["id"],"resolution_status":row["resolution_status"]}] if row else [])
        if self.operation=="upsert":
            row={**self.payload,"id":"uuid-1"};self.rows[row["polymarket_market_id"]]=row
            return SimpleNamespace(data=[row])
        row=self.rows[next(iter(self.rows))];row.update(self.payload)
        return SimpleNamespace(data=[row])


class FakeDB:
    def __init__(self):self.markets=MarketsTable()
    def table(self,name):assert name=="markets";return self.markets


def test_market_upsert_is_idempotent_and_preserves_review():
    db=FakeDB();repo=Repository(db)
    row={"polymarket_market_id":"123","question":"Highest temperature?","resolution_status":"needs_review"}
    assert repo.upsert_market(row)==("uuid-1",True)
    db.markets.rows["123"]["resolution_status"]="verified"
    assert repo.upsert_market({**row,"question":"Updated question"})==("uuid-1",False)
    assert len(db.markets.rows)==1
    assert db.markets.rows["123"]["question"]=="Updated question"
    assert db.markets.rows["123"]["resolution_status"]=="verified"
