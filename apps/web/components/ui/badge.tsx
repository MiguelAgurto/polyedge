import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";
export function Badge({
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border border-[var(--border)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        className,
      )}
      {...props}
    />
  );
}
