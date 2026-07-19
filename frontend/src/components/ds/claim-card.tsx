import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import type { TrustLevel } from "./trust-badge";
import { TrustBadge } from "./trust-badge";

const borderColor: Record<TrustLevel, string> = {
  high: "var(--verified)",
  med: "var(--contested-amber)",
  low: "var(--dim)",
  contradicted: "var(--contested-red)",
};

/**
 * Paper-colored card over the ink desk. 3px left border in trust color.
 * The `id` attaches an anchor point that the evidence thread can draw from.
 */
export function ClaimCard({
  trust,
  id,
  claimId,
  quote,
  meta,
  children,
  className,
  onClick,
  active = false,
}: {
  trust: TrustLevel;
  id?: string;
  claimId?: string;
  quote?: string;
  meta?: ReactNode;
  children?: ReactNode;
  className?: string;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <div
      id={id}
      onClick={onClick}
      className={cn(
        "group relative rounded-md bg-[var(--paper)] text-[var(--ink)] p-6 md:p-7",
        "border-l-[3px] transition-shadow duration-150",
        "shadow-[0_1px_0_0_rgba(0,0,0,0.02)]",
        onClick && "cursor-pointer hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.45)]",
        active && "shadow-[0_10px_28px_-14px_rgba(0,0,0,0.55)]",
        className,
      )}
      style={{ borderLeftColor: borderColor[trust] }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {claimId && (
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
              {claimId}
            </div>
          )}
          {quote && (
            <blockquote className="mt-2 border-l-2 border-[var(--ink)]/15 pl-3 font-mono text-sm leading-relaxed text-[var(--ink)]/85">
              &ldquo;{quote}&rdquo;
            </blockquote>
          )}
          {children && <div className="mt-3 text-sm text-[var(--ink)]/80">{children}</div>}
        </div>
        <TrustBadge level={trust} />
      </div>
      {meta && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-[var(--ink)]/10 pt-3 font-mono text-[11px] text-[var(--ink)]/55">
          {meta}
        </div>
      )}
    </div>
  );
}
