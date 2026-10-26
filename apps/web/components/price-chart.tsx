"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import type { Snapshot, Token } from "@/types/database";
import { date } from "@/lib/utils";
export function PriceChart({
  snapshots,
  tokens,
  timeZone,
}: {
  snapshots: Snapshot[];
  tokens: Token[];
  timeZone: string;
}) {
  const names = new Map(tokens.map((t) => [t.token_id, t.outcome]));
  const grouped = new Map<
    string,
    { time: string; YES?: number; NO?: number }
  >();
  snapshots
    .slice()
    .reverse()
    .forEach((s) => {
      const time = s.captured_at;
      const row = grouped.get(time) ?? { time };
      const name = names.get(s.token_id);
      if (name && s.best_ask != null) row[name] = Number(s.best_ask);
      grouped.set(time, row);
    });
  const data = Array.from(grouped.values());
  if (!data.length)
    return (
      <p className="muted py-12 text-center text-sm">
        No price snapshots collected yet.
      </p>
    );
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis
            dataKey="time"
            tickFormatter={(v) => new Date(v).toLocaleDateString("en-US", { timeZone })}
            stroke="#8b98a5"
            fontSize={11}
          />
          <YAxis domain={[0, 1]} stroke="#8b98a5" fontSize={11} />
          <Tooltip
            contentStyle={{
              background: "#121922",
              border: "1px solid #253040",
            }}
            labelFormatter={(v) => date(String(v), timeZone)}
          />
          <Legend />
          <Line
            dataKey="YES"
            type="monotone"
            stroke="#00d4aa"
            dot={false}
            connectNulls
          />
          <Line
            dataKey="NO"
            type="monotone"
            stroke="#8ca7ff"
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
