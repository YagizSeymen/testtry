import { cn } from "@/lib/utils";

/**
 * Founder Score with visible ± range and a bracket/whisker showing the band
 * graphically. Never a progress bar — this is a confidence interval.
 *
 * Score is 0–100. Band is one-sided (e.g. ±22).
 */
export function UncertaintyBand({
  score,
  band,
  className,
  compact = false,
}: {
  score: number;
  band: number;
  className?: string;
  compact?: boolean;
}) {
  const lo = Math.max(0, score - band);
  const hi = Math.min(100, score + band);
  const leftPct = lo;
  const widthPct = hi - lo;

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            "font-mono font-medium text-[var(--ink)]",
            compact ? "text-2xl" : "text-4xl tracking-tight",
          )}
        >
          {score}
        </span>
        <span
          className={cn(
            "font-mono text-[var(--ink)]/60",
            compact ? "text-xs" : "text-sm",
          )}
        >
          ±{band}
        </span>
      </div>

      {/* Bracket / whisker */}
      <div className="relative mt-2 h-3 w-full">
        {/* baseline axis */}
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-[var(--ink)]/15" />
        {/* band bar with end caps */}
        <div
          className="absolute top-1/2 -translate-y-1/2"
          style={{
            left: `${leftPct}%`,
            width: `${widthPct}%`,
          }}
        >
          {/* end caps */}
          <span className="absolute left-0 top-1/2 h-2.5 w-px -translate-y-1/2 bg-[var(--ink)]/60" />
          <span className="absolute right-0 top-1/2 h-2.5 w-px -translate-y-1/2 bg-[var(--ink)]/60" />
          {/* bar */}
          <span className="absolute top-1/2 left-0 h-px w-full -translate-y-1/2 bg-[var(--ink)]/50" />
          {/* score marker */}
          <span
            className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 bg-[var(--signal)]"
            style={{
              left: `${((score - lo) / Math.max(1, hi - lo)) * 100}%`,
            }}
          />
        </div>
      </div>

      {!compact && (
        <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--ink)]/40">
          <span>{lo}</span>
          <span>{hi}</span>
        </div>
      )}
    </div>
  );
}
