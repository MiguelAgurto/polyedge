import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink } from "lucide-react";
import { PriceChart } from "@/components/price-chart";
import { Freshness, Status } from "@/components/status";
import { Card } from "@/components/ui/card";
import { getEnsembleVotes, getLatestForecasts, getMarket, getSnapshots, getTokens } from "@/lib/data";
import { detailExplanation } from "@/lib/plain-english";
import { date, day, price } from "@/lib/utils";
import { getTimeZonePreference } from "@/lib/timezone-server";
export const dynamic = "force-dynamic";
export default async function MarketDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const [market, tokens, snapshots, votes, forecasts, preference] = await Promise.all([
    getMarket(id),
    getTokens(id),
    getSnapshots(id),
    getEnsembleVotes(),
    getLatestForecasts(),
    getTimeZonePreference(),
  ]);
  const timeZone = preference.timeZone;
  if (!market) notFound();
  const yesToken = tokens.find((token) => token.outcome === "YES");
  const noToken = tokens.find((token) => token.outcome === "NO");
  const yesBook = snapshots.find(
    (snapshot) => snapshot.token_id === yesToken?.token_id,
  );
  const noBook = snapshots.find(
    (snapshot) => snapshot.token_id === noToken?.token_id,
  );
  const explanation = detailExplanation(
    market.market_type,
    market.resolution_status,
    yesBook,
    noBook,
    timeZone,
  );
  const vote = votes.find((item) => item.market_id === id);
  const forecast = forecasts.find((item) => item.id === vote?.forecast_id && item.location_kind === "station_coordinates");
  const meta: [string, string | null | undefined][] = [
    ["Polymarket ID", market.polymarket_market_id],
    ["Condition ID", market.condition_id],
    ["Event ID", market.event_id],
    ["Market type", market.market_type],
    ["City", market.city],
    ["Country", market.country],
    ["Station", market.station_id],
    ["Target date", day(market.target_date)],
    ["Timezone", market.timezone],
    [
      "Threshold",
      market.threshold &&
        `${market.threshold}°${market.temperature_unit ?? ""}`,
    ],
    ["Operator", market.comparison_operator],
    ["Resolution source", market.resolution_source],
    ["Closes", date(market.end_at, timeZone)],
  ];
  return (
    <div className="space-y-5">
      <Link href="/markets" className="muted text-xs">
        ← Back to markets
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="panel-title mb-2">Contract detail</p>
          <h1 className="max-w-4xl text-2xl font-semibold leading-tight">
            {market.question}
          </h1>
          <div className="mt-4 flex flex-wrap gap-2">
            <Status value={market.market_status} />
            <Status value={market.resolution_status} />
            {market.market_url && (
              <a
                href={market.market_url}
                target="_blank"
                rel="noopener noreferrer"
                className="accent flex items-center gap-1 text-xs"
              >
                Open on Polymarket <ExternalLink size={13} />
              </a>
            )}
          </div>
        </div>
        <Freshness
          at={[yesBook?.captured_at, noBook?.captured_at]
            .filter(Boolean)
            .sort()
            .at(0)}
        />
      </div>
      <Card className="p-5">
        <h2 className="panel-title mb-3">What this means</h2>
        <div className="max-w-4xl space-y-2 text-sm leading-6">
          {explanation.map((sentence) => (
            <p key={sentence}>{sentence}</p>
          ))}
          <p className="muted">
            In the books below, “best bid” is the highest price a buyer offered,
            “best ask” is the lowest price a seller listed, and “ask depth” is
            the number of shares listed for sale.
          </p>
        </div>
      </Card>
      <Card className="p-5">
        <h2 className="panel-title mb-3">Independent weather research</h2>
        {vote && forecast ? (
          <div className="max-w-4xl space-y-2 text-sm leading-6">
            <p>{vote.yes_members} of {vote.total_members} Open-Meteo model scenarios
              meet this contract&apos;s whole-degree temperature rule.</p>
            <p className="muted">The forecast uses coordinates for {forecast.location_name}
              {" "}({forecast.station_id}), saved {date(forecast.collected_at, timeZone)}. The model grid is
              {" "}{forecast.grid_distance_km?.toFixed(1)} km from that station. The settlement
              day and historical accuracy still need checking. This count is not a calibrated
              probability or a buy signal.</p>
            <Link href="/signals" className="accent text-xs">See all weather research →</Link>
          </div>
        ) : (
          <p className="muted text-sm">No matching independent forecast has been collected for this contract yet.</p>
        )}
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        {(["YES", "NO"] as const).map((outcome) => {
          const token = tokens.find((t) => t.outcome === outcome);
          const book = snapshots.find((s) => s.token_id === token?.token_id);
          return (
            <Card key={outcome} className="p-5">
              <div className="mb-5 flex justify-between">
                <h2 className="panel-title">{outcome} order book</h2>
                <span className="mono muted text-xs">
                  {token?.asset_kind ?? "—"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="muted text-xs">Best bid</div>
                  <div className="metric mt-1">{price(book?.best_bid)}</div>
                </div>
                <div>
                  <div className="muted text-xs">Best ask</div>
                  <div className="metric accent mt-1">
                    {price(book?.best_ask)}
                  </div>
                </div>
                <div>
                  <div className="muted text-xs">Spread</div>
                  <div className="mono mt-1">{price(book?.spread)}</div>
                </div>
                <div>
                  <div className="muted text-xs">Ask depth (shares)</div>
                  <div className="mono mt-1">{book?.ask_liquidity ?? "—"}</div>
                </div>
              </div>
              <div className="muted mt-5 break-all border-t border-[var(--border)] pt-4 text-xs">
                Asset ID: {token?.token_id ?? "Unavailable"}
                <br />
                Captured: {date(book?.captured_at, timeZone)}
              </div>
            </Card>
          );
        })}
      </div>
      <Card className="p-5">
        <h2 className="panel-title mb-5">Ask price history</h2>
        <PriceChart snapshots={snapshots} tokens={tokens} timeZone={timeZone} />
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="panel-title mb-5">Contract metadata</h2>
          <dl className="space-y-3">
            {meta.map(([key, value]) => (
              <div
                key={key}
                className="flex justify-between gap-4 border-b border-[var(--border)] pb-2 text-sm"
              >
                <dt className="muted">{key}</dt>
                <dd className="max-w-[60%] break-all text-right mono">
                  {value || "—"}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card className="p-5">
          <h2 className="panel-title mb-4">Resolution and description</h2>
          <p className="muted whitespace-pre-wrap text-sm leading-6">
            {market.description || "No description supplied."}
          </p>
          <div className="mt-6 border-t border-[var(--border)] pt-5">
            <div className="panel-title mb-3">Resolution rules</div>
            <p className="muted whitespace-pre-wrap text-sm leading-6">
              {market.resolution_rules ||
                "No explicit rules supplied. Manual review required."}
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
