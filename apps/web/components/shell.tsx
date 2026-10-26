import Link from "next/link";
import {
  Activity,
  BarChart3,
  CloudSun,
  Radar,
  Settings2,
  Table2,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import { AutoRefresh } from "@/components/auto-refresh";
import { TimeZoneSelector } from "@/components/timezone-selector";
import { getTimeZonePreference } from "@/lib/timezone-server";

const nav = [
  { href: "/", label: "Overview", icon: Activity },
  { href: "/markets", label: "Markets", icon: Table2 },
  { href: "/signals", label: "Signals", icon: Radar },
  { href: "/traders", label: "Traders", icon: Users },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings2 },
];
export async function Shell({ children }: { children: ReactNode }) {
  const { selected, timeZone } = await getTimeZonePreference();
  const zones = ["UTC", ...Intl.supportedValuesOf("timeZone")];
  return (
    <div className="min-h-screen lg:flex">
      <AutoRefresh />
      <aside className="border-b border-[var(--border)] bg-[var(--surface)] lg:min-h-screen lg:w-[220px] lg:border-b-0 lg:border-r">
        <div className="flex h-16 items-center gap-3 border-b border-[var(--border)] px-5">
          <CloudSun size={21} className="accent" />
          <div>
            <div className="text-base font-bold tracking-tight">
              PolyEdge<span className="accent">.</span>
            </div>
            <div className="muted text-[10px] tracking-[.16em] uppercase">
              Find the edge.
            </div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto p-3 lg:block lg:space-y-1">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex min-w-max items-center gap-3 rounded px-3 py-2.5 text-sm text-[var(--muted)] hover:bg-[var(--surface2)] hover:text-[var(--text)]"
            >
              <item.icon size={16} />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="muted hidden px-6 pt-8 text-[11px] uppercase tracking-widest lg:block">
          Read-only intelligence
        </div>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-3 md:px-8">
          <span className="muted text-xs uppercase tracking-[.18em]">
            Weather market intelligence
          </span>
          <div className="flex flex-wrap items-center gap-3">
            <TimeZoneSelector selected={selected} timeZone={timeZone} zones={zones} />
            <span className="mono rounded border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--accent)]">
              PUBLIC DATA · READ ONLY
            </span>
          </div>
        </header>
        <div className="mx-auto max-w-[1500px] p-5 md:p-8">{children}</div>
      </main>
    </div>
  );
}
