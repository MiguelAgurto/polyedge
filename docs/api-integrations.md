# Public API integration

Verified against the [current Polymarket market discovery documentation](https://docs.polymarket.com/market-data/discover-markets), [market details documentation](https://docs.polymarket.com/market-data/market-details) and [prices and order books documentation](https://docs.polymarket.com/market-data/prices-order-books).

- `GET https://gamma-api.polymarket.com/public-search?q=highest%20temperature`: returns recent matching events with child markets. The scanner pages with the live-verified `limit_per_type` and `page` parameters, then validates and fetches market details.
- `GET https://gamma-api.polymarket.com/tags/slug/weather`: resolves the current weather tag ID at runtime.
- `GET https://gamma-api.polymarket.com/markets/keyset?closed=false&tag_id=ID&limit=N`: returns `markets` and `next_cursor`; subsequent pages use `after_cursor`. If tag lookup fails, scanning falls back to the general market feed and records an error.
- `GET https://gamma-api.polymarket.com/markets/{id}`: full metadata including `question`, `description`, `events`, `outcomes`, `clobTokenIds` for CTF, and `positionIds` for V2.
- `GET https://gamma-api.polymarket.com/events/{id}`: event metadata and URL slug when an event ID is present.
- `GET https://clob.polymarket.com/book?token_id={asset_id}`: public outcome book, with `asset_id`, optional millisecond `timestamp`, `bids`, `asks`, `price` and `size`.

Gamma outcome labels and identifiers are validated as a two-entry YES/NO mapping before book collection. V2 `positionIds` are stored with `asset_kind='position'`; CTF `clobTokenIds` use `asset_kind='token'`. An explicit `resolutionSource` is preserved when present. No displayed probability, `lastTradePrice`, or Gamma `bestAsk` is substituted for a book quote. Bid/ask arrays are reduced by numeric maximum/minimum, so response ordering changes do not alter the result. Missing sides stay null.

The client only offers public GET methods, a timeout, exponential backoff with jitter, `Retry-After` handling for rate limits, and validation errors for malformed responses. It does not call authenticated CLOB endpoints.

## Open-Meteo Phase 2 research

- [Geocoding API](https://open-meteo.com/en/docs/geocoding-api): `GET https://geocoding-api.open-meteo.com/v1/search` supplies a candidate timezone for each station's nearby city. The `Seoul (Incheon)` market uses an Incheon city search. The geocoded country code must match the NOAA station country code.
- [Ensemble API](https://open-meteo.com/en/docs/ensemble-api): `GET https://ensemble-api.open-meteo.com/v1/ensemble` requests `daily=temperature_2m_max`, `models=gfs_seamless`, seven forecast days, the NOAA station's coordinates and the candidate timezone. Member arrays and the returned grid coordinates are archived locally.
- [NOAA Aviation Weather API](https://aviationweather.gov/data/api/): `stationinfo` resolves explicit ICAO station IDs from weather.gov market rules to airport coordinates; `metar` supplies recent airport temperature reports. The API offers up to 30 days of recent observations. The local collector requests 24 hours per station on each run and deduplicates reports.
- [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api): `temperature_2m_previous_day1` supplies a forecast 24 hours before each valid hour. The local backfill groups 24 hourly values by station local day and requires at least 20 valid hours.
- NOAA `metar` supports bounded historical `date` and `hours` requests. The backfill requests daily UTC windows for pairs of stations, respects the public request rate, deduplicates readings, and retries failed windows. A local day needs at least 18 distinct observation hours spanning 20 hours.
- Gamma `feeSchedule` for current weather markets gives taker rate 0.05 with exponent 1. The signal uses the [published weather fee formula](https://help.polymarket.com/en/articles/13364478-trading-fees), fee per share = rate × ask × (1 − ask), rounded to five decimals. A missing or different schedule blocks a buy call.
- A model grid may differ from the named airport point, and Aviation Weather METAR reports may differ from the exact weather.gov time series table cited by a contract. Signal probabilities are short-sample empirical estimates, not verified settlement probabilities; buy labels are provisional research.
