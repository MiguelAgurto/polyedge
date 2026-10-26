# Roadmap

## Phase 1: current milestone

Read-only market discovery, conservative normalization, order-book collection, local persistence with optional Supabase storage, scanner observability and a data-backed dashboard. A local watcher can refresh markets and prices automatically. Manual verification is required before treating a contract as a precisely modeled weather event.

## Phase 2: local research signals built

1. **Built:** collect Open-Meteo GFS ensemble daily high forecasts hourly at NOAA airport station coordinates, archive runs for 90 days, and show uncalibrated scenario counts beside contracts and prices.
2. **Built:** extract explicit station IDs from market resolution URLs, match stations against NOAA Aviation Weather metadata, and archive recent METAR temperatures for 30 days.
3. **Built:** backfill 28 complete days of 24-hour-ahead GFS hourly forecasts and station observations. Validate forecast error on the latest seven days before generating an empirical probability estimate.
4. **Built:** compare stressed, conservative probability bounds against fresh YES/NO best asks and each market's weather taker fee. Show BUY YES, BUY NO or NO BUY with a plain-English reason. The app remains read-only.
5. **Next:** verify the exact weather.gov settlement time series and fallback rules, then add paper trading and realized performance evaluation with the default paper bankroll of $250. More history is needed for stronger probability calibration.

Later research may include alerts, additional weather categories and more robust scheduling.
