import Link from "next/link";
import {
  ArrowUpRight,
  Database,
  Radio,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Freshness, Status } from "@/components/status";
import { count, getLatestSnapshotAt, getMarkets, getRuns, getSignals } from "@/lib/data";
import { date, isStale, price } from "@/lib/utils";
import { getTimeZonePreference } from "@/lib/timezone-server";

export const dynamic = "force-dynamic";
export default async function Overview() {
  const [markets, runs, total, activeCount, reviewCount, latestSnapshotAt, signals, preference] =
    await Promise.all([
      getMarkets(),
      getRuns(),
      count("markets"),
      count("markets", {
        market_status: "eq.active",
        market_type: "eq.daily_max_temperature",
      }),
      count("markets", { resolution_status: "eq.needs_review" }),
      getLatestSnapshotAt(),
      getSignals(),
      getTimeZonePreference(),
    ]);
  const timeZone = preference.timeZone;
  const liveBuys = signals.filter((signal) => signal.signal.startsWith("BUY") && !isStale(signal.generated_at, 20));
  const last = runs.find((r) => r.status === "success");
  const latest = runs[0];
  const metrics = [
    { label: "Weather markets", value: total, icon: Database },
    { label: "Active monitored", value: activeCount, icon: Radio },
    { label: "Need verification", value: reviewCount, icon: ShieldCheck },
    {
      label: "Snapshots, last run",
      value: latest?.snapshots_created ?? "—",
      icon: Timer,
    },
  ];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="panel-title mb-2">System overview</p>
          <h1 className="page-title">Weather market monitor</h1>
        </div>
        <div className="muted text-xs">
          Last successful scan:{" "}
          <span className="text-[var(--text)]">{date(last?.completed_at, timeZone)}</span>
        </div>
      </div>
      <Card className="p-5">
        <h2 className="panel-title mb-3">In plain English</h2>
        <p className="max-w-4xl text-sm leading-6">
          Your local scanner found {total} weather markets. {activeCount} are
          active daily high temperature markets that it can monitor.
          {latestSnapshotAt
            ? ` The latest order-book data was saved ${date(latestSnapshotAt, timeZone)}${isStale(latestSnapshotAt) ? ", so prices may have moved." : "."}`
            : " No order-book data has been saved yet."}
        </p>
        <p className="muted mt-2 max-w-4xl text-sm leading-6">
          The prices shown are offers from Polymarket traders. The signal check
          currently finds {liveBuys.length} buy calls after comparing recent
          weather history with fresh YES and NO asks and fees. These are local
          research calls, and no orders are placed. <Link href="/signals" className="accent">See every decision and its reason →</Link>
        </p>
      </Card>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((m) => (
          <Card key={m.label} className="p-5">
            <div className="mb-5 flex items-center justify-between">
              <span className="panel-title">{m.label}</span>
              <m.icon size={16} className="muted" />
            </div>
            <div className="metric">{m.value}</div>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--border)] p-5">
            <h2 className="panel-title">Recent market activity</h2>
            <Link
              href="/markets"
              className="accent flex items-center gap-1 text-xs"
            >
              All markets <ArrowUpRight size={14} />
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Status</th>
                  <th>YES ask</th>
                  <th>Book</th>
                </tr>
              </thead>
              <tbody>
                {markets.slice(0, 8).map((m) => {
                  const yes = m.market_tokens.find((t) => t.outcome === "YES")
                    ?.market_snapshots[0];
                  return (
                    <tr key={m.id}>
                      <td className="max-w-[420px]">
                        <Link href={`/markets/${m.id}`} className="font-medium">
                          {m.question}
                        </Link>
                        <div className="muted mt-1 text-xs">
                          {m.city ?? "Location unknown"} ·{" "}
                          {m.market_type.replaceAll("_", " ")}
                        </div>
                      </td>
                      <td>
                        <Status value={m.resolution_status} />
                      </td>
                      <td className="mono">{price(yes?.best_ask)}</td>
                      <td>
                        <Freshness at={yes?.captured_at} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {markets.length === 0 && (
              <p className="muted p-8 text-center">
                No discovered markets yet. Run the scanner to populate this
                view.
              </p>
            )}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="panel-title mb-6">Scanner health</h2>
          <div className="space-y-5 text-sm">
            <div className="flex justify-between">
              <span className="muted">Latest run</span>
              {latest ? <Status value={latest.status} /> : <span>—</span>}
            </div>
            <div className="flex justify-between">
              <span className="muted">Started</span>
              <span className="mono text-xs">{date(latest?.started_at, timeZone)}</span>
            </div>
            <div className="flex justify-between">
              <span className="muted">Errors</span>
              <span className="mono">{latest?.errors_count ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="muted">Data freshness</span>
              <Freshness at={latestSnapshotAt} />
            </div>
          </div>
          <Link
            href="/analytics"
            className="accent mt-8 inline-flex items-center gap-1 text-xs"
          >
            View run history <ArrowUpRight size={14} />
          </Link>
        </Card>
      </div>
    </div>
  );
}
