import { cn } from "@/lib/utils";

export type TrendKind = "up" | "flat" | "down";

/**
 * Thin geometric trend glyph. Colored green / gray / red. Never an emoji.
 */
export function TrendArrow({
  trend,
  className,
}: {
  trend: TrendKind;
  className?: string;
}) {
  const color =
    trend === "up"
      ? "var(--verified)"
      : trend === "down"
        ? "var(--contested-red)"
        : "var(--dim)";

  return (
    <svg
      viewBox="0 0 16 16"
      aria-label={`trend ${trend}`}
      className={cn("h-3.5 w-3.5", className)}
      style={{ color }}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
    >
      {trend === "up" && (
        <>
          <path d="M3 12 L13 4" />
          <path d="M8 4 L13 4 L13 9" />
        </>
      )}
      {trend === "down" && (
        <>
          <path d="M3 4 L13 12" />
          <path d="M8 12 L13 12 L13 7" />
        </>
      )}
      {trend === "flat" && <path d="M3 8 L13 8" />}
    </svg>
  );
}
