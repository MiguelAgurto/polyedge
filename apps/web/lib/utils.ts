import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { DEFAULT_TIME_ZONE } from "@/lib/timezones";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function money(value: number | string | null | undefined) {
  return value == null ? "—" : `$${Number(value).toFixed(3)}`;
}
export function price(value: number | string | null | undefined) {
  return value == null ? "—" : `${(Number(value) * 100).toFixed(1)}¢`;
}
export function date(value: string | null | undefined, timeZone = DEFAULT_TIME_ZONE) {
  return value
    ? new Date(value).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone,
        timeZoneName: "short",
      })
    : "—";
}
export function day(value: string | null | undefined) {
  return value
    ? new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      })
    : "—";
}
export function isStale(value: string | null | undefined, minutes = 15) {
  return !value || Date.now() - new Date(value).getTime() > minutes * 60_000;
}
