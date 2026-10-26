import Link from "next/link";
import { Card } from "@/components/ui/card";
import { RefreshDataButton } from "@/components/refresh-data-button";
import { getMarkets, getSignals, getTraderResearch } from "@/lib/data";
import { date, isStale, price } from "@/lib/utils";
import type { TraderFill } from "@/types/database";
import { getTimeZonePreference } from "@/lib/timezone-server";

export const dynamic = "force-dynamic";

function rank(value: number | null | undefined, checked: string | undefined) {
  if (!checked) return "—";
  return value == null ? "Outside top 100" : `#${value}`;
}

function pnl(value: number | null | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
    signDisplay: "exceptZero",
  }).format(value);
}

export default async function Traders() {
  const [traders, markets, signals, preference] = await Promise.all([
    getTraderResearch(), getMarkets(), getSignals(), getTimeZonePreference(),
  ]);
  const timeZone = preference.timeZone;
  const signalByMarket = new Map(signals.map((signal) => [signal.market_id, signal]));
  const quoteByToken = new Map(markets.filter((market) => market.market_status === "active")
    .flatMap((market) => market.market_tokens.map((token) => ({ market, token })))
    .map(({ market, token }) => [token.token_id, {
      market, quote: token.market_snapshots[0], signal: signalByMarket.get(market.id),
    }] as const));
  const fills = traders.flatMap((trader) => (trader.recent_fills ?? []).map((fill) => ({ trader, fill })))
    .sort((a, b) => (b.fill.timestamp ?? "").localeCompare(a.fill.timestamp ?? ""))
    .slice(0, 40);
  const lastUpdate = traders.reduce<string | null>((latest, trader) =>
    !latest || (trader.updated_at && trader.updated_at > latest) ? trader.updated_at ?? latest : latest, null);
  const stale = isStale(lastUpdate, 15);

  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="panel-title mb-2">Public wallet research</p><h1 className="page-title">Weather traders</h1>
        <p className="muted mt-2 text-sm">Latest saved check: {date(lastUpdate, timeZone)} · {stale ? "Waiting for fresh data" : "Current snapshot"}</p></div>
      <RefreshDataButton />
    </div>
    <Card className="p-5">
      <h2 className="panel-title mb-3">In plain English</h2>
      <p className="max-w-4xl text-sm leading-6">This tab watches six public Polymarket wallets that are worth studying for weather markets. It shows where they stand on the weather leaderboard and their latest publicly reported high-temperature trades. A successful trader&apos;s earlier price may no longer be available to you.</p>
      <p className="muted mt-2 max-w-4xl text-sm leading-6">The app checks these wallets when it updates its market data: with the existing local watcher, or when you press “Get latest data.” Opening this page does not call Polymarket. The latest-trades view is a sample of each wallet&apos;s most recent 100 fills across all categories, so it can miss earlier weather trades. This is research, not a buy signal.</p>
    </Card>
    {traders.length === 0 ? <Card className="p-8 text-center"><p className="font-medium">No trader snapshot yet.</p><p className="muted mt-2 text-sm">Press “Get latest data” to check the public watchlist with the next market update.</p></Card> :
      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">{traders.map((trader) => <Card key={trader.wallet} className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div><a href={trader.profile_url} target="_blank" rel="noopener noreferrer" className="text-lg font-semibold hover:underline">{trader.name} ↗</a><p className="muted mt-1 text-xs">{trader.role}</p></div>
          <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${isStale(trader.updated_at, 15) ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"}`}>{isStale(trader.updated_at, 15) ? "Stale" : "Updated"}</span>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2 text-sm">
          {(["all", "month", "week"] as const).map((period) => <div key={period}><p className="panel-title">{period === "all" ? "All time" : period}</p><p className="mt-1 font-semibold">{rank(trader.rank?.[period], trader.rank_updated_at)}</p><p className="muted mt-1 text-xs">{pnl(trader.pnl?.[period])}</p></div>)}
        </div>
        <p className="muted mt-4 text-xs">{trader.sample_temperature_fills ?? 0} high-temperature fills in latest {trader.sample_fills ?? 0} fills · {trader.sample_markets ?? 0} markets</p>
        <p className="muted mt-1 text-xs">Last public trade: {date(trader.last_trade_at, timeZone)} · Checked {date(trader.checked_at, timeZone)}</p>
        {trader.last_error && <p className="mt-3 text-xs text-amber-700 dark:text-amber-300">Some data could not be refreshed; older values may be shown.</p>}
      </Card>)}</div>}
    <Card className="overflow-hidden">
      <div className="border-b border-[var(--border)] p-5"><h2 className="panel-title">Recent high-temperature fills</h2><p className="muted mt-2 text-sm">The trader&apos;s price is their recorded fill. “Our ask” is the latest saved price to buy the same token, when PolyEdge tracks that active market. It can change or disappear.</p></div>
      <div className="overflow-x-auto"><table><thead><tr><th>Time</th><th>Trader</th><th>Market and side</th><th>Their fill</th><th>Our ask now</th><th>Our signal</th></tr></thead><tbody>
        {fills.map(({ trader, fill }, index) => {
          const match = fill.token_id ? quoteByToken.get(fill.token_id) : undefined;
          const quote = match?.quote;
          const usableQuote = quote && !isStale(quote.captured_at, 15);
          const signal = match?.signal;
          return <tr key={`${trader.wallet}-${fill.condition_id}-${fill.timestamp}-${index}`}>
            <td className="min-w-32 text-xs">{date(fill.timestamp, timeZone)}</td>
            <td><a href={trader.profile_url} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">{trader.name}</a></td>
            <td className="min-w-72 max-w-[420px]"><FillTitle fill={fill} /><div className="muted mt-1 text-xs">{fill.side} {fill.outcome}</div></td>
            <td className="mono">{price(fill.price)}<div className="muted mt-1 text-xs">{fill.size?.toFixed(0) ?? "—"} shares</div></td>
            <td className="mono">{usableQuote ? price(quote.best_ask) : "—"}{match && <div className="muted mt-1 text-xs">{usableQuote ? "Saved live quote" : "Quote stale"}</div>}</td>
            <td>{match && signal && !isStale(signal.generated_at, 20) ? <Link href={`/markets/${match.market.id}`} className="font-medium hover:underline">{signal.signal}</Link> : "—"}</td>
          </tr>;
        })}
      </tbody></table>{fills.length === 0 && <p className="muted p-8 text-center">No recent high-temperature fills in the saved sample.</p>}</div>
    </Card>
    <p className="muted text-xs">Source: <a href="https://data-api.polymarket.com/v2/docs" target="_blank" rel="noopener noreferrer" className="accent">Polymarket Data API v2</a>. All-time leaderboard P&amp;L uses realized results; week and month use changes in marked equity. Those figures are not directly comparable. No trades are placed.</p>
  </div>;
}

function FillTitle({ fill }: { fill: TraderFill }) {
  return fill.market_url ? <a href={fill.market_url} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">{fill.title} ↗</a> : <span className="font-medium">{fill.title}</span>;
}
