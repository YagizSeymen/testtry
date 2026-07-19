import { cn } from "@/lib/utils";

export type TrustLevel = "high" | "med" | "low" | "contradicted";

const styles: Record<TrustLevel, string> = {
  high: "bg-[color-mix(in_oklab,var(--verified)_18%,transparent)] text-[var(--verified)] ring-1 ring-inset ring-[color-mix(in_oklab,var(--verified)_40%,transparent)]",
  med: "bg-[color-mix(in_oklab,var(--contested-amber)_18%,transparent)] text-[var(--contested-amber)] ring-1 ring-inset ring-[color-mix(in_oklab,var(--contested-amber)_40%,transparent)]",
  low: "bg-[color-mix(in_oklab,var(--dim)_18%,transparent)] text-[var(--dim)] ring-1 ring-inset ring-[color-mix(in_oklab,var(--dim)_40%,transparent)]",
  contradicted:
    "bg-[color-mix(in_oklab,var(--contested-red)_18%,transparent)] text-[var(--contested-red)] ring-1 ring-inset ring-[color-mix(in_oklab,var(--contested-red)_45%,transparent)]",
};

/**
 * Trust badge — never color alone. Always paired with the word.
 */
export function TrustBadge({
  level,
  className,
}: {
  level: TrustLevel;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider",
        styles[level],
        className,
      )}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: "currentColor" }}
      />
      {level}
    </span>
  );
}
