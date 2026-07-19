import { cn } from "@/lib/utils";

export type OriginKind = "github" | "hn" | "inbound" | "synthetic";

const label: Record<OriginKind, string> = {
  github: "github",
  hn: "hn",
  inbound: "inbound",
  synthetic: "synthetic",
};

/**
 * Origin chip. Synthetic data always renders with a dashed border so it can
 * never be visually confused with real scraped data.
 */
export function OriginTag({
  origin,
  className,
}: {
  origin: OriginKind;
  className?: string;
}) {
  const isSynthetic = origin === "synthetic";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest",
        "text-[var(--ink)]/60",
        isSynthetic
          ? "border border-dashed border-[var(--ink)]/25"
          : "border border-solid border-[var(--ink)]/10 bg-[var(--ink)]/5",
        className,
      )}
    >
      {label[origin]}
    </span>
  );
}
