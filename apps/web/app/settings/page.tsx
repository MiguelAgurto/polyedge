import { Card } from "@/components/ui/card";
import { hasLocalData, health } from "@/lib/data";
import { getTimeZonePreference } from "@/lib/timezone-server";
export const dynamic = "force-dynamic";
export default async function Settings() {
  const [gamma, clob, localData, preference] = await Promise.all([
    health(
      "https://gamma-api.polymarket.com/markets/keyset?closed=false&limit=1",
    ),
    health("https://clob.polymarket.com/book"),
    hasLocalData(),
    getTimeZonePreference(),
  ]);
  const rows = [
    ["Scanner mode", "Read-only public API"],
    ["Gamma API", gamma ? "Reachable" : "Unavailable"],
    ["CLOB API", clob ? "Reachable" : "Unavailable"],
    ["Local data", localData ? "Available" : "No scan recorded yet"],
    ["Displayed times", `${preference.timeZone}${preference.selected === "auto" ? " (device time zone)" : " (selected)"}`],
    ["Market discovery", "Every 30 minutes while the local scanner is running"],
    ["Order-book collection", "Every 5 minutes while the local scanner is running"],
    ["Dashboard", "Refreshes every 30 seconds while this tab is visible"],
    ["Application version", "0.1.0"],
  ];
  return (
    <div className="space-y-5">
      <div>
        <p className="panel-title mb-2">System</p>
        <h1 className="page-title">Settings</h1>
        <p className="muted mt-2 text-sm">
          Read-only configuration and connectivity. Keep the local scanner
          running to update prices automatically.
        </p>
      </div>
      <Card className="max-w-3xl p-5">
        <h2 className="panel-title mb-6">Configuration</h2>
        <dl>
          {rows.map(([label, value]) => (
            <div
              key={label}
              className="flex flex-wrap justify-between gap-3 border-b border-[var(--border)] py-3 text-sm"
            >
              <dt className="muted">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
