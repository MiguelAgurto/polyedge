import { cn } from "@/lib/utils";
import type { InputHTMLAttributes } from "react";
export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]",
        className,
      )}
      {...props}
    />
  );
}
