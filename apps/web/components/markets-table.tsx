"use client";
import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Freshness, Status } from "@/components/status";
import { day, price } from "@/lib/utils";
import { marketQuoteSummary } from "@/lib/plain-english";
import type { MarketRow } from "@/types/database";

export function MarketsTable({ markets }: { markets: MarketRow[] }) {
  const [search, setSearch] = useState("");
  const [city, setCity] = useState("");
  const [status, setStatus] = useState("");
  const [resolution, setResolution] = useState("");
  const [target, setTarget] = useState("");
  const cities = Array.from(
    new Set(markets.map((m) => m.city).filter((v): v is string => Boolean(v))),
  ).sort();
  const filtered = markets.filter(
    (m) =>
      m.question.toLowerCase().includes(search.toLowerCase()) &&
      (!city || m.city === city) &&
      (!status || m.market_status === status) &&
      (!resolution || m.resolution_status === resolution) &&
      (!target || m.target_date === target),
  );
  return (
    <>
      <div className="grid gap-3 p-4 md:grid-cols-[2fr_1fr_1fr_1fr_1fr]">
        <div className="relative">
          <Search className="muted absolute left-3 top-2.5" size={15} />
          <Input
            aria-label="Search markets"
            placeholder="Search market questions"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="City"
          value={city}
          onChange={(e) => setCity(e.target.value)}
        >
          <option value="">All cities</option>
          {cities.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="Market status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All market states</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="closed">Closed</option>
        </select>
        <select
          aria-label="Resolution status"
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
        >
          <option value="">All verification</option>
          <option value="needs_review">Needs review</option>
          <option value="verified">Verified</option>
          <option value="rejected">Rejected</option>
        </select>
        <Input
          aria-label="Target date"
          type="date"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
      </div>
      <div className="muted px-4 pb-3 text-xs">
        Showing {filtered.length} of {markets.length} loaded markets
      </div>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Market</th>
              <th>City</th>
              <th>Target date</th>
              <th>YES ask</th>
              <th>NO ask</th>
              <th>Spread</th>
              <th>Liquidity</th>
              <th>Resolution</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => {
              const yes = m.market_tokens.find((t) => t.outcome === "YES")
                ?.market_snapshots[0];
              const no = m.market_tokens.find((t) => t.outcome === "NO")
                ?.market_snapshots[0];
              const liquidity =
                Number(yes?.ask_liquidity ?? 0) +
                Number(no?.ask_liquidity ?? 0);
              const updated = [yes?.captured_at, no?.captured_at]
                .filter(Boolean)
                .sort()
                .at(0);
              return (
                <tr key={m.id}>
                  <td className="max-w-[360px] min-w-[250px]">
                    <Link href={`/markets/${m.id}`} className="font-medium">
                      {m.question}
                    </Link>
                    <div className="muted mt-1 text-xs">
                      {m.market_type.replaceAll("_", " ")}
                    </div>
                    <div className="mt-2 max-w-[350px] text-xs leading-5 text-[var(--text)]">
                      {marketQuoteSummary(m)}
                    </div>
                  </td>
                  <td>{m.city ?? "—"}</td>
                  <td className="whitespace-nowrap">{day(m.target_date)}</td>
                  <td className="mono">{price(yes?.best_ask)}</td>
                  <td className="mono">{price(no?.best_ask)}</td>
                  <td className="mono">{price(yes?.spread)}</td>
                  <td className="mono">
                    {liquidity ? liquidity.toFixed(2) : "—"}
                  </td>
                  <td>
                    <Status value={m.resolution_status} />
                  </td>
                  <td>
                    <Freshness at={updated} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="muted p-8 text-center">
            No markets match these filters.
          </p>
        )}
      </div>
    </>
  );
}
