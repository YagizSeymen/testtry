import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * Explicit "not yet run" card. Every nullable pipeline stage renders one of
 * these — never a blank space, never a generic spinner.
 */
export function NotYetRun({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-md border border-dashed border-[var(--ink)]/20 bg-[var(--paper)] p-6",
        className,
      )}
    >
      <div className="flex items-start gap-4">
        <div
          aria-hidden
          className="mt-1 h-8 w-8 shrink-0 rounded-sm border border-[var(--ink)]/15"
          style={{
            backgroundImage:
              "repeating-linear-gradient(45deg, transparent 0 4px, color-mix(in oklab, var(--ink) 8%, transparent) 4px 5px)",
          }}
        />
        <div className="flex-1">
          <h3 className="font-display text-sm font-medium tracking-tight text-[var(--ink)]/90">
            {title}
          </h3>
          <p className="mt-1 text-sm text-[var(--ink)]/60">{description}</p>
          {action && <div className="mt-4">{action}</div>}
        </div>
      </div>
    </div>
  );
}
