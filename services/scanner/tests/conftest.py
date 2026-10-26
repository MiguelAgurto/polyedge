import pytest


@pytest.fixture
def market_data():
    return {
        "id": "703257", "version": "v1", "slug": "highest-temperature-in-london-on-october-18-2099",
        "question": "Highest temperature in London on October 18 2099?",
        "description": "Market resolves from official weather observations.",
        "resolutionSource": "https://example.org/weather-observations",
        "conditionId": "0x747dc809fb79e1b05be09c42d6179459a58de2ef3e40f02484a4e1260f741f75",
        "outcomes": '["Yes","No"]', "clobTokenIds": '["107505882767731489358349912513945399560393482969656700824895970500493757150417","7305630249804085635496399869905769372294302716159034447326228509068694952392"]',
        "events": [{"id":"90177"}], "active": True, "closed": False, "acceptingOrders": True,
        "endDate": "2099-10-19T00:00:00Z"
    }


@pytest.fixture
def book_data():
    return {"market":"0x747d", "asset_id":"107505882767731489358349912513945399560393482969656700824895970500493757150417", "timestamp":"1782753357257", "bids":[{"price":"0.10","size":"12"},{"price":"0.12","size":"8"}], "asks":[{"price":"0.30","size":"10"},{"price":"0.25","size":"5"}]}
