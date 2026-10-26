import { Badge } from "@/components/ui/badge";
import { isStale } from "@/lib/utils";
export function Status({ value }: { value: string }) {
  const good =
    value === "verified" || value === "success" || value === "active";
  return (
    <Badge
      className={
        good
          ? "border-emerald-900 bg-emerald-950 text-emerald-400"
          : value === "needs_review" || value === "partial"
            ? "border-amber-900 bg-amber-950 text-amber-400"
            : "text-[var(--muted)]"
      }
    >
      {value.replaceAll("_", " ")}
    </Badge>
  );
}
export function Freshness({ at }: { at: string | null | undefined }) {
  return (
    <Badge
      className={
        isStale(at)
          ? "border-amber-900 text-amber-400"
          : "border-emerald-900 text-emerald-400"
      }
    >
      {isStale(at) ? "STALE" : "FRESH"}
    </Badge>
  );
}
