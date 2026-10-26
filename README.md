# PolyEdge

PolyEdge is a read-only Polymarket weather-market monitor. It discovers public weather contracts, records executable YES/NO order-book quotes, and displays stored data in a Next.js dashboard. Phase 2 checks archived GFS forecasts against airport observations, estimates contract chances from recent forecast errors, and displays BUY YES, BUY NO, or NO BUY research decisions. It does not connect a wallet or place orders.

## Architecture

- `services/scanner`: Python 3.12+ CLI using public Gamma and CLOB GET endpoints, with validation, retries and per-market error recording.
- `data/polyedge.json`: local scanner output, written atomically and read by the dashboard. The file is ignored by Git.
- `apps/web`: Next.js App Router dashboard reading the local data file on the server.
- `supabase/migrations`: optional PostgreSQL schema for a later hosted setup.

See [how it works](#how-it-works), [the project status map](docs/project-status.md), [architecture](docs/architecture.md), [API integration notes](docs/api-integrations.md), [roadmap](docs/roadmap.md), and the separate [weather trader research watchlist](docs/trader-watchlist.md).

## How it works

### Online deployment

The dashboard runs on Netlify. Appwrite runs the scanner every 60 minutes and
stores the latest compressed scanner state in a private bucket. The dashboard
reads that state on the server, so Appwrite credentials never reach a visitor's
browser. The **Get latest data** button queues the same Appwrite scanner job.

Set these server-only Netlify variables before publishing:

```text
APPWRITE_ENDPOINT=https://fra.cloud.appwrite.io/v1
APPWRITE_PROJECT_ID=6adf6632003217d76f0b
APPWRITE_API_KEY=<server API key>
APPWRITE_DATABASE_ID=polyedge
APPWRITE_STATE_TABLE_ID=state_pointers
APPWRITE_STATE_BUCKET_ID=polyedge-state
APPWRITE_SCANNER_FUNCTION_ID=polyedge-scanner
```

`APPWRITE_API_KEY` needs only the Appwrite scopes needed to read rows and
files, and to create function executions. Never use `NEXT_PUBLIC_` for it.

1. The scanner discovers active public Polymarket weather contracts and keeps only the supported daily maximum-temperature markets.
2. It reads the public YES and NO order books, saves the best executable prices and liquidity, and records failures without stopping the rest of the scan.
3. For markets with an explicit NOAA airport station in their rules, it collects GFS ensemble forecasts and airport observations. It also maintains a short historical sample to measure forecast error.
4. The signal engine turns the ensemble and historical errors into a cautious chance estimate, compares it with the current ask and applicable fee, and explains a `BUY YES`, `BUY NO`, or `NO BUY` research decision.
5. The Next.js dashboard reads the saved data and presents markets, scan health, signals, trader research, and refresh controls. It is read-only: PolyEdge never connects a wallet or submits an order.

For delivery status, completed work, active constraints, and the next tasks, see the [project status map](docs/project-status.md).

## Prerequisites

- Python 3.12 or newer
- Node.js 20.9 or newer and npm
- Network access to public Polymarket, Open-Meteo and NOAA Aviation Weather APIs

No paid scheduler, wallet, or trading account is needed.

## Installation

```sh
cp .env.example .env
python3.12 -m venv services/scanner/.venv
services/scanner/.venv/bin/pip install -e 'services/scanner[test]'
npm install --prefix apps/web
```

No account, API key, or environment file is required for local use. The scanner creates `data/polyedge.json` automatically. Both processes must run from this repository. To move the data file, set `POLYEDGE_DATA_FILE` to the same absolute path for the scanner and web process.

| Variable | Purpose | Default |
| --- | --- | --- |
| `POLYEDGE_DISCOVERY_LIMIT` | Maximum active market candidates examined per discovery run | `100` |
| `POLYEDGE_PAGE_SIZE` | Gamma keyset page size | `50` |
| `POLYEDGE_REQUEST_TIMEOUT` | HTTP timeout, seconds | `10` |
| `POLYEDGE_MAX_RETRIES` | Retries for timeouts, 429 and 5xx | `3` |
| `POLYEDGE_STORAGE` | Scanner storage backend | `local` |
| `POLYEDGE_DATA_FILE` | Shared local data file | `<repo>/data/polyedge.json` |
| `SUPABASE_URL` | Supabase project URL | unset |
| `SUPABASE_SERVICE_ROLE_KEY` | Trusted server-side database key | unset |

## Optional Supabase setup

Create a Supabase project and run `supabase/migrations/202610120001_phase1.sql` in its SQL editor, or apply it using the Supabase CLI. The migration creates `markets`, `market_tokens`, `market_snapshots`, `scanner_runs`, `scanner_errors` and a latest-snapshot view. RLS is enabled and anonymous/authenticated access is revoked. Keep the service role key only in trusted local or server environments.

The scanner can write there with `--storage supabase`; the local dashboard reads the JSON file, so local storage is the default workflow.

## Run the scanner

From the repository root:

```sh
PYTHONPATH=services/scanner services/scanner/.venv/bin/python -m polyedge.jobs.discover_markets --mode all
PYTHONPATH=services/scanner services/scanner/.venv/bin/python -m polyedge.jobs.discover_markets --mode discover
PYTHONPATH=services/scanner services/scanner/.venv/bin/python -m polyedge.jobs.discover_markets --mode snapshots
```

`--dry-run` reads real public data, prints JSON lines, and needs no Supabase credentials. `all` discovers and snapshots; `discover` only refreshes markets; `snapshots` only reads the stored active supported assets. The CLI exits nonzero when scan errors occur. A local nonblocking file lock prevents concurrent scanner processes on the same machine.

The first command above populates the dashboard. Re-run it whenever you want fresh data. A dry run only prints data; it does not fill the dashboard.

For automatic local updates, keep this running in a second terminal:

```sh
services/scanner/.venv/bin/python -m polyedge.jobs.run_local
```

It scans immediately, then checks for new markets every 30 minutes, refreshes order books every 5 minutes, collects Open-Meteo forecasts and NOAA airport observations every 60 minutes, and refreshes archived one-day-ahead forecasts daily. Stop it with Ctrl+C. Only one watcher can run at a time, and it skips a cycle if a manual job is already running. Markets that passed their closing time stop receiving new order-book snapshots.

It also recomputes signals and refreshes the six-wallet weather trader watchlist after each price scan. Trader data comes from Polymarket's public Data API v2; there is no separate trader polling job. Before the first signal run on a new machine, backfill recent public weather history once:

```sh
services/scanner/.venv/bin/python -m polyedge.jobs.backfill_history
services/scanner/.venv/bin/python -m polyedge.jobs.retry_history
services/scanner/.venv/bin/python -m polyedge.jobs.generate_signals
```

The backfill requests 28 complete local days from Open-Meteo and NOAA Aviation Weather. `retry_history` only revisits any NOAA windows that timed out. These commands use local JSON storage and public GET APIs. Pause the watcher while running them, since the local writer lock keeps jobs sequential.

To collect forecasts once without running the watcher:

```sh
PYTHONPATH=services/scanner services/scanner/.venv/bin/python -m polyedge.jobs.collect_forecasts
PYTHONPATH=services/scanner services/scanner/.venv/bin/python -m polyedge.jobs.collect_observations
```

Forecasts, station observations, historical checks, signals and trader research use local JSON storage; no Supabase account or API key is needed. The file keeps forecast runs for 90 days and station observations for 30 days. If a trader API request fails, the saved snapshot remains visible with an error and its original timestamp.

For a launchd or cron setup, schedule `--mode all` every 30 minutes, `--mode snapshots` every 5 minutes, and both collection jobs hourly. The lock prevents overlapping jobs. Do not run the watcher and scheduled jobs together.

## Run the dashboard

```sh
npm run dev --prefix apps/web
```

Open `http://localhost:3000/signals` for the buy check or `http://localhost:3000/traders` for the public trader watchlist. While the browser tab is visible, the dashboard reloads saved local data every 30 seconds. The **Get latest data** button runs a new local market, weather, price, signal, and trader check immediately and then updates the page. Opening the Traders page only reads the saved snapshot; it does not call Polymarket. The Signals page explains every current decision in plain English.

Use the time zone selector in the dashboard header to choose any supported time zone or **Device time zone (automatic)**. The choice is saved in this browser. Automatic mode detects the device's time zone again when the page opens or becomes visible, so displayed times follow the device as you travel. With no device setting yet, the dashboard starts in Europe/Podgorica time. A contract's target date remains the date in that market's question.

The estimate compares each airport's daily METAR maximum with its archived GFS forecast at a fixed 24-hour lead. It requires at least 21 complete days, uses the most recent seven days for a rolling validation check, and uses the full history's forecast errors to estimate today's contract chance. The displayed cautious range uses a 95% Wilson interval and shifts today's model high by at least 1°C (or 1.64 ensemble standard deviations). A BUY label requires a fresh best ask with at least 20 shares and $5 at that price, a known weather taker fee, and at least five percentage points of conservative edge after the ask and fee. Otherwise the decision is NO BUY. The signal check runs locally and never submits an order.

## Verification

```sh
services/scanner/.venv/bin/pytest services/scanner/tests
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

Unit tests use mocked API responses and do not require live Polymarket access. A dry run is the public API smoke test. Local storage requires no external database.

## Current limits

- Daily maximum temperature classification is conservative. Ambiguous temperature contracts are stored as `unsupported` for review. No contract is automatically marked verified.
- Recent temperature discovery uses Gamma public search, then a bounded weather-tag pass. This prioritizes current contracts without scanning the entire historical tag feed.
- City and date are parsed only from explicit question text. An ICAO station ID is read only from an explicit NOAA resolution URL. The NOAA Aviation Weather station record supplies its coordinates; the nearby city's Open-Meteo geocoding result supplies a candidate timezone. Neither step verifies the contract's settlement day or fallback rules.
- The markets table loads the 500 most recently updated records. Overview counts use exact database counts.
- Local storage keeps the latest 48 snapshots per token, about four hours at the usual five-minute cadence. A market page shows up to 200 recent rows. Quotes are top of book; bid and ask liquidity sum resting size across the respective sides of the book, in shares.
- Scanner freshness is based on stored timestamps; scheduling and manual resolution verification are operator tasks.
- Open-Meteo GFS forecasts use each airport's coordinates, but the model evaluates a nearby weather grid, 0.9–31.5 km from the eight current stations. The historical check measures errors against NOAA Aviation Weather METAR maxima, which are a proxy for the weather.gov time series named in the market rules. The exact settlement values, fallback rules, and corrections remain unverified. A 28-day sample is short, the interval does not account for every market or model risk, and historical weather accuracy is not a profit backtest. Treat buy labels as provisional research.
- The Phase 2 collector uses local storage only. The optional Supabase path remains Phase 1 market data storage.
- Open-Meteo's free endpoint is for non-commercial use and requires attribution. The Signals page credits Open-Meteo; a commercial deployment would need an appropriate data licence.

## Next milestone

Verify the exact weather.gov settlement series against archived METARs, then keep a paper record of signal outcomes and simulated fills. More settled days will allow stronger probability calibration and a real profit backtest.
## Private Netlify access

The deployed dashboard uses HTTP Basic Authentication. Set `POLYEDGE_SITE_PASSWORD`
as a Netlify secret and sign in with the username `miguel`. This app-level gate keeps
the dashboard private on Netlify's free plan, where platform password protection is
not available.
