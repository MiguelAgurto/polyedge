"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function RefreshDataButton() {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");

  async function refresh() {
    setRunning(true);
    setMessage("Checking markets, weather, prices, signals, and traders…");
    try {
      const response = await fetch("/api/refresh", { method: "POST", cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Refresh failed.");
      if (result.queued) {
        setMessage("The refresh is running in Appwrite. This page will show the new data when it finishes.");
        return;
      }
      const summary = result.summary as Record<string, { errors_count?: number; buy_yes?: number; buy_no?: number; updated?: number }>;
      router.refresh();
      const warnings = Object.values(summary).reduce((count, part) => count + (part.errors_count ?? 0), 0);
      setMessage(`Updated. ${summary.signals?.buy_yes ?? 0} BUY YES and ${summary.signals?.buy_no ?? 0} BUY NO signals; ${summary.traders?.updated ?? 0} trader profiles checked.${warnings ? ` ${warnings} data checks had errors.` : ""}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Refresh failed. Please try again.");
    } finally {
      setRunning(false);
    }
  }

  return <div className="flex flex-col items-start gap-1 sm:items-end">
    <button type="button" onClick={refresh} disabled={running}
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium hover:border-[var(--accent)] disabled:cursor-wait disabled:opacity-60">
      {running ? "Getting latest data…" : "Get latest data"}
    </button>
    <span aria-live="polite" className="muted max-w-xs text-xs">{message}</span>
  </div>;
}
