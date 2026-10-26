"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { DEVICE_TIME_ZONE_COOKIE, TIME_ZONE_COOKIE, validTimeZone } from "@/lib/timezones";

const COOKIE_AGE = 60 * 60 * 24 * 365;
const QUICK_ZONES = [
  "Europe/Podgorica", "Europe/London", "America/New_York",
  "America/Los_Angeles", "Asia/Dubai", "Asia/Singapore",
  "Asia/Tokyo", "Australia/Sydney", "UTC",
];

function saveCookie(name: string, value: string) {
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${COOKIE_AGE}; SameSite=Lax`;
}

function deviceTimeZone() {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return validTimeZone(zone) ? zone : null;
}

export function TimeZoneSelector({ selected, timeZone, zones }: {
  selected: string;
  timeZone: string;
  zones: string[];
}) {
  const router = useRouter();
  useEffect(() => {
    const syncDeviceZone = () => {
      if (document.visibilityState !== "visible") return;
      const detected = deviceTimeZone();
      if (!detected) return;
      const saved = document.cookie.split("; ")
        .find((part) => part.startsWith(`${DEVICE_TIME_ZONE_COOKIE}=`))?.split("=")[1];
      if (saved !== encodeURIComponent(detected)) {
        saveCookie(DEVICE_TIME_ZONE_COOKIE, detected);
        if (selected === "auto") router.refresh();
      }
    };
    syncDeviceZone();
    document.addEventListener("visibilitychange", syncDeviceZone);
    return () => document.removeEventListener("visibilitychange", syncDeviceZone);
  }, [selected, router]);

  function change(value: string) {
    if (value !== "auto" && !zones.includes(value)) return;
    saveCookie(TIME_ZONE_COOKIE, value);
    const detected = deviceTimeZone();
    if (detected) saveCookie(DEVICE_TIME_ZONE_COOKIE, detected);
    router.refresh();
  }

  return <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
    <span className="hidden sm:inline">Time zone</span>
    <select key={selected} aria-label="Display time zone" defaultValue={selected} onChange={(event) => change(event.target.value)}
      className="max-w-[210px] rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-xs text-[var(--text)]">
      <option value="auto">Device time zone (automatic)</option>
      <optgroup label="Quick choices">
        {QUICK_ZONES.map((zone) => <option key={zone} value={zone}>{zone.replaceAll("_", " ")}</option>)}
      </optgroup>
      <optgroup label="All time zones">
        {zones.filter((zone) => !QUICK_ZONES.includes(zone)).map((zone) =>
          <option key={zone} value={zone}>{zone.replaceAll("_", " ")}</option>)}
      </optgroup>
    </select>
    <span className="hidden text-[11px] lg:inline">{timeZone}</span>
  </label>;
}
