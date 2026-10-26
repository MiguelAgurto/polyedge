create extension if not exists pgcrypto;

create table if not exists public.markets (
  id uuid primary key default gen_random_uuid(),
  polymarket_market_id text not null unique,
  condition_id text,
  event_id text,
  question text not null,
  description text,
  market_url text,
  market_type text not null check (market_type in ('daily_max_temperature','unsupported')),
  city text,
  country text,
  station_id text,
  target_date date,
  timezone text,
  threshold numeric,
  temperature_unit text check (temperature_unit in ('C','F')),
  comparison_operator text check (comparison_operator in ('gt','gte','lt','lte','eq')),
  resolution_source text,
  resolution_rules text,
  resolution_status text not null default 'needs_review' check (resolution_status in ('needs_review','verified','rejected')),
  market_status text not null check (market_status in ('active','suspended','closed')),
  end_at timestamptz,
  raw_metadata jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.polyedge_set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
create trigger markets_updated_at before update on public.markets
for each row execute function public.polyedge_set_updated_at();

create table if not exists public.market_tokens (
  id uuid primary key default gen_random_uuid(),
  market_id uuid not null references public.markets(id) on delete cascade,
  token_id text not null unique,
  asset_kind text not null check (asset_kind in ('token','position')),
  outcome text not null check (outcome in ('YES','NO')),
  unique (market_id, outcome),
  unique (market_id, token_id)
);

create table if not exists public.market_snapshots (
  id bigint generated always as identity primary key,
  market_id uuid not null references public.markets(id) on delete cascade,
  token_id text not null,
  best_bid numeric check (best_bid > 0 and best_bid < 1),
  best_ask numeric check (best_ask > 0 and best_ask < 1),
  spread numeric check (spread >= 0),
  bid_liquidity numeric check (bid_liquidity >= 0),
  ask_liquidity numeric check (ask_liquidity >= 0),
  captured_at timestamptz not null default now(),
  api_timestamp timestamptz,
  raw_orderbook jsonb not null,
  foreign key (market_id, token_id) references public.market_tokens(market_id, token_id)
);

create table if not exists public.scanner_runs (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  mode text not null check (mode in ('all','discover','snapshots')),
  status text not null check (status in ('running','success','partial','failed')),
  markets_discovered integer not null default 0,
  markets_updated integer not null default 0,
  snapshots_created integer not null default 0,
  errors_count integer not null default 0
);

create table if not exists public.scanner_errors (
  id bigint generated always as identity primary key,
  scanner_run_id uuid not null references public.scanner_runs(id) on delete cascade,
  market_id text,
  error_type text not null,
  error_message text not null,
  created_at timestamptz not null default now()
);

create index if not exists markets_status_date_idx on public.markets(market_status, target_date);
create index if not exists markets_resolution_idx on public.markets(resolution_status);
create index if not exists markets_city_idx on public.markets(city);
create index if not exists snapshots_market_captured_idx on public.market_snapshots(market_id, captured_at desc);
create index if not exists snapshots_token_captured_idx on public.market_snapshots(token_id, captured_at desc);
create index if not exists runs_started_idx on public.scanner_runs(started_at desc);
create index if not exists errors_run_idx on public.scanner_errors(scanner_run_id, created_at desc);

alter table public.markets enable row level security;
alter table public.market_tokens enable row level security;
alter table public.market_snapshots enable row level security;
alter table public.scanner_runs enable row level security;
alter table public.scanner_errors enable row level security;
revoke all on public.markets, public.market_tokens, public.market_snapshots, public.scanner_runs, public.scanner_errors from anon, authenticated;
revoke all on sequence public.market_snapshots_id_seq, public.scanner_errors_id_seq from anon, authenticated;

create or replace view public.latest_market_snapshots with (security_invoker = true) as
select distinct on (token_id) id, market_id, token_id, best_bid, best_ask, spread,
  bid_liquidity, ask_liquidity, captured_at, api_timestamp
from public.market_snapshots order by token_id, captured_at desc, id desc;
revoke all on public.latest_market_snapshots from anon, authenticated;
