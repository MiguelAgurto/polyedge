import "server-only";
import { cookies } from "next/headers";
import { DEFAULT_TIME_ZONE, DEVICE_TIME_ZONE_COOKIE, TIME_ZONE_COOKIE, validTimeZone } from "@/lib/timezones";

export async function getTimeZonePreference() {
  const store = await cookies();
  const requested = store.get(TIME_ZONE_COOKIE)?.value;
  const selected = requested && requested !== "auto" && validTimeZone(requested) ? requested : "auto";
  const device = store.get(DEVICE_TIME_ZONE_COOKIE)?.value;
  const timeZone = selected === "auto"
    ? validTimeZone(device) ? device : DEFAULT_TIME_ZONE
    : selected;
  return { selected, timeZone };
}
