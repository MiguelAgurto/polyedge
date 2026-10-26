import Link from "next/link";
import { Card } from "@/components/ui/card";
import { RefreshDataButton } from "@/components/refresh-data-button";
import { getMarkets, getSignals } from "@/lib/data";
import { day, isStale, price } from "@/lib/utils";

export const dynamic = "force-dynamic";
const pct = (value: number | null | undefined) => value == null ? "—" : `${Math.round(value * 100)}%`;

export default async function Signals() {
  const [markets, signals] = await Promise.all([getMarkets(), getSignals()]);
  const byMarket = new Map(signals.map((signal) => [signal.market_id, signal]));
  const rows = markets.filter((market) => market.market_status === "active" &&
    market.market_type === "daily_max_temperature")
    .map((market) => ({ market, signal: byMarket.get(market.id) }))
    .sort((a, b) => Number(b.signal?.signal.startsWith("BUY")) - Number(a.signal?.signal.startsWith("BUY")) ||
      (a.market.city ?? "").localeCompare(b.market.city ?? "") || a.market.question.localeCompare(b.market.question));
  const buys = rows.filter(({ signal }) => signal?.signal.startsWith("BUY") && !isStale(signal.generated_at, 20));
  const stationStats = new Map(signals.filter((signal) => signal.station_id && signal.validation.history_days)
    .map((signal) => [signal.station_id!, signal.validation]));

  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="panel-title mb-2">Local weather research</p><h1 className="page-title">Buy YES or NO signals</h1></div><RefreshDataButton /></div>
    <Card className="p-5">
      <h2 className="panel-title mb-3">In plain English</h2>
      <p className="max-w-4xl text-sm leading-6">{signals.length === 0
        ? "The first check is running. It needs past airport readings, past forecasts, and fresh buy prices."
        : buys.length > 0
          ? `${buys.length} of ${rows.length} active contracts currently pass the buy check. Each call compares a cautious weather estimate with the live price and trading fee.`
          : "No active contract currently passes the buy check. A BUY label appears only when the weather estimate clears the live price, trading fee, and a safety margin."}</p>
      <p className="muted mt-2 max-w-4xl text-sm leading-6">The estimate uses recent days when both a 24-hour-ahead forecast and airport reading were available. Later days test how well it worked. The cautious range also allows the model temperature to shift by at least 1°C. These are research signals, not orders or guarantees. The market&apos;s official settlement reading may differ from the airport reports used here.</p>
    </Card>
    {buys.length > 0 && <div className="grid gap-3 lg:grid-cols-2">{buys.slice(0, 8).map(({ market, signal }) =>
      <Card key={market.id} className="p-5">
        <div className="flex items-center justify-between gap-3"><span className="panel-title">{market.city} · {day(market.target_date)}</span><span className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-700 dark:text-emerald-300">{signal!.signal}</span></div>
        <Link href={`/markets/${market.id}`} className="mt-3 block font-medium leading-6 hover:underline">{market.question}</Link>
        <p className="mt-3 text-sm">{signal!.reason}</p>
        <p className="muted mt-2 text-xs">Estimated YES chance {pct(signal!.yes_probability)} · cautious range {pct(signal!.yes_range_low)}–{pct(signal!.yes_range_high)}</p>
        <p className="muted mt-1 text-xs">{signal!.best_side} ask {price(signal!.best_ask)} · fee {price(signal!.fee_per_share)} per share · {signal!.quote_size?.toFixed(0)} shares at the best ask</p>
        {market.resolution_status !== "verified" && <p className="muted mt-2 text-xs">Research signal · official settlement source has not been independently verified.</p>}
      </Card>)}</div>}
    <Card className="overflow-hidden">
      <div className="border-b border-[var(--border)] p-5"><h2 className="panel-title">Every active contract</h2><p className="muted mt-2 text-sm">“NO BUY” means the data or price did not clear our checks; it does not mean the outcome will be NO.</p></div>
      <div className="overflow-x-auto"><table>
        <thead><tr><th>Contract</th><th>YES chance</th><th>Cautious range</th><th>Best side and ask</th><th>Decision and reason</th></tr></thead>
        <tbody>{rows.map(({ market, signal }) => {
          const stale = signal && isStale(signal.generated_at, 20);
          return <tr key={market.id}>
            <td className="max-w-[420px]"><Link href={`/markets/${market.id}`} className="font-medium">{market.question}</Link><div className="muted mt-1 text-xs">{market.city} · {day(market.target_date)}</div></td>
            <td className="mono">{pct(signal?.yes_probability)}</td>
            <td className="mono">{pct(signal?.yes_range_low)}–{pct(signal?.yes_range_high)}</td>
            <td className="mono text-xs">{signal?.best_side ? `${signal.best_side} · ${price(signal.best_ask)}` : "—"}</td>
            <td className="max-w-[340px]"><span className={signal?.signal.startsWith("BUY") && !stale ? "font-bold text-emerald-700 dark:text-emerald-300" : "font-medium"}>{stale ? "STALE" : signal?.signal ?? "WAITING"}</span><div className="muted mt-1 text-xs">{stale ? "Waiting for the next live check." : signal?.reason ?? "The first check has not completed."}</div></td>
          </tr>;
        })}</tbody>
      </table>{rows.length === 0 && <p className="muted p-8 text-center">No active weather contracts found.</p>}</div>
    </Card>
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{[...stationStats].sort(([a], [b]) => a.localeCompare(b)).map(([station, stats]) =>
      <Card key={station} className="p-5"><div className="panel-title">{station}</div><div className="metric mt-3">{stats.history_days} days</div><p className="muted mt-2 text-xs">Complete airport days compared with earlier forecasts</p><p className="mt-3 text-sm">Later-day average error: {stats.holdout_mae_c?.toFixed(1) ?? "—"}°C across {stats.holdout_days ?? 0} checks</p></Card>)}</div>
    <p className="muted text-xs">Weather data: <a href="https://open-meteo.com/en/docs/previous-runs-api" target="_blank" rel="noopener noreferrer" className="accent">Open-Meteo archived GFS</a> and <a href="https://aviationweather.gov/data/api/" target="_blank" rel="noopener noreferrer" className="accent">NOAA Aviation Weather METAR</a>. Prices and fees: Polymarket. No trades are placed.</p>
  </div>;
}
