# Architecture

The scanner is a single process with three modes. Discovery uses Gamma's keyset market feed, filters candidate questions, fetches full market details and optionally the parent event, then normalizes metadata. Supported binary contracts yield validated outcome asset IDs. CLOB GET order-book responses become immutable snapshots with best bid, best ask, spread and top-level sizes. Errors are recorded per market without aborting the rest of the run.

`markets.polymarket_market_id` is unique. Market rows and outcome rows are upserted; snapshots append over time. Each execution gets a `scanner_runs` row. The file lock prevents overlapping jobs on one host.

By default, the scanner writes one local JSON data file atomically after each run. The dashboard reads that file in Next.js server components; client components receive only public market rows for filtering and chart rendering. The scanner can also write to optional Supabase storage, but the local dashboard reads the JSON file. Production deployment should protect access if the operator does not intend the market research to be public.

The optional local watcher runs discovery and order-book collection in one process, with a separate singleton lock and the scanner's per-run lock. It marks markets past their closing time as suspended before selecting tokens for new snapshots. Local storage retains the most recent 48 snapshots per token. The dashboard refreshes its server-rendered data every 30 seconds while the tab is visible.

Extension points for forecast ingestion and modeling belong in new scanner packages and tables. They should consume normalized contracts and verified resolution metadata, leaving Polymarket collection independent of any probability model.
