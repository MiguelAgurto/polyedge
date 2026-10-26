export const DEFAULT_TIME_ZONE = "Europe/Podgorica";
export const TIME_ZONE_COOKIE = "polyedge_time_zone";
export const DEVICE_TIME_ZONE_COOKIE = "polyedge_device_time_zone";

export function validTimeZone(value: string | undefined): value is string {
  if (!value || value.length > 80) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}
