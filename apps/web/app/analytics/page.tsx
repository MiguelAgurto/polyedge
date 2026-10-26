import { Card } from "@/components/ui/card";
import { Freshness, Status } from "@/components/status";
import { getErrors, getLatestSnapshotAt, getRuns } from "@/lib/data";
import { date } from "@/lib/utils";
import { getTimeZonePreference } from "@/lib/timezone-server";
export const dynamic = "force-dynamic";
export default async function Analytics() {
  const [runs, errors, latestSnapshotAt, preference] = await Promise.all([
    getRuns(),
    getErrors(),
    getLatestSnapshotAt(),
    getTimeZonePreference(),
  ]);
  const timeZone = preference.timeZone;
  return (
    <div className="space-y-5">
      <div>
        <p className="panel-title mb-2">Operations</p>
        <h1 className="page-title">Scanner analytics</h1>
        <p className="muted mt-2 text-sm">
          Collection history, API failures and data freshness. No trading
          results are shown.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-5">
          <div className="panel-title">Runs loaded</div>
          <div className="metric mt-5">{runs.length}</div>
        </Card>
        <Card className="p-5">
          <div className="panel-title">Snapshots in loaded runs</div>
          <div className="metric mt-5">
            {runs.reduce((n, r) => n + r.snapshots_created, 0)}
          </div>
        </Card>
        <Card className="p-5">
          <div className="panel-title">Latest data</div>
          <div className="mt-6">
            <Freshness at={latestSnapshotAt} />
          </div>
        </Card>
      </div>
      <Card className="overflow-hidden">
        <h2 className="panel-title border-b border-[var(--border)] p-5">
          Run history
        </h2>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Started</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Discovered</th>
                <th>Updated</th>
                <th>Snapshots</th>
                <th>Errors</th>
                <th>Completed</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="mono whitespace-nowrap text-xs">
                    {date(r.started_at, timeZone)}
                  </td>
                  <td>{r.mode}</td>
                  <td>
                    <Status value={r.status} />
                  </td>
                  <td className="mono">{r.markets_discovered}</td>
                  <td className="mono">{r.markets_updated}</td>
                  <td className="mono">{r.snapshots_created}</td>
                  <td className="mono">{r.errors_count}</td>
                  <td className="mono whitespace-nowrap text-xs">
                    {date(r.completed_at, timeZone)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!runs.length && (
            <p className="muted p-8 text-center">No scanner runs recorded.</p>
          )}
        </div>
      </Card>
      <Card className="overflow-hidden">
        <h2 className="panel-title border-b border-[var(--border)] p-5">
          Recent scanner errors
        </h2>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Market ID</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {errors.map((e) => (
                <tr key={e.id}>
                  <td className="mono whitespace-nowrap text-xs">
                    {date(e.created_at, timeZone)}
                  </td>
                  <td>{e.error_type}</td>
                  <td className="mono">{e.market_id ?? "—"}</td>
                  <td className="max-w-[600px] break-words">
                    {e.error_message}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!errors.length && (
            <p className="muted p-8 text-center">No errors recorded.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
