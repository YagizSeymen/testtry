import { useEffect, useLayoutEffect, useRef, useState, useCallback, useMemo } from "react";
import type { TrustLevel } from "./trust-badge";

/**
 * Evidence thread status — maps 1:1 to the color matrix specified in the
 * design system. Consumers pass either `status` (preferred) or a legacy
 * `trust` value which is mapped through `trustToStatus`.
 */
export type EvidenceStatus =
  | "supported"
  | "contested-core"
  | "contested-peripheral"
  | "unverifiable";

const STATUS_COLOR: Record<EvidenceStatus, string> = {
  supported: "#3F7D58",
  "contested-core": "#B23A34",
  "contested-peripheral": "#C08A2E",
  unverifiable: "#8A8F98",
};

const trustToStatus = (t: TrustLevel): EvidenceStatus => {
  switch (t) {
    case "high":
    case "med":
      return "supported";
    case "contradicted":
      return "contested-core";
    case "low":
    default:
      return "unverifiable";
  }
};

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * useEvidenceThread — hover coordination for a claim ↔ signal pair.
 * Returns bind props to spread on both endpoint elements and an `active` flag
 * the <EvidenceThread /> reads to draw. Hovering either end lights the wire.
 */
export function useEvidenceThread() {
  const [active, setActive] = useState(false);
  const on = useCallback(() => setActive(true), []);
  const off = useCallback(() => setActive(false), []);
  const bind = useMemo(
    () => ({
      onMouseEnter: on,
      onMouseLeave: off,
      onFocus: on,
      onBlur: off,
    }),
    [on, off]
  );
  return { active, bind, setActive };
}

type BaseProps = {
  fromId: string;
  toId: string;
  container: React.RefObject<HTMLElement | null>;
  active?: boolean;
};

type StatusProps = BaseProps & { status: EvidenceStatus; trust?: never };
type TrustProps = BaseProps & { trust: TrustLevel; status?: never };

/**
 * Evidence thread — signature motif.
 *
 * Renders a 1px cubic-bezier curve between two DOM nodes inside `container`.
 * The line only draws when `active` is true (hover / focus driven by parent),
 * animating stroke-dashoffset over 400ms ease-out to feel like current
 * illuminating down a copper wire. Respects prefers-reduced-motion by
 * rendering instantly at full opacity.
 */
export function EvidenceThread(props: StatusProps | TrustProps) {
  const { fromId, toId, container, active = true } = props;
  const status: EvidenceStatus =
    "status" in props && props.status
      ? props.status
      : trustToStatus((props as TrustProps).trust);
  const color = STATUS_COLOR[status];

  const [path, setPath] = useState<string | null>(null);
  const pathRef = useRef<SVGPathElement | null>(null);
  const [length, setLength] = useState(0);
  const reduced = useRef(prefersReducedMotion());

  useLayoutEffect(() => {
    if (!active) return;
    const compute = () => {
      const root = container.current;
      const from = document.getElementById(fromId);
      const to = document.getElementById(toId);
      if (!root || !from || !to) return;
      const r = root.getBoundingClientRect();
      const a = from.getBoundingClientRect();
      const b = to.getBoundingClientRect();
      const x1 = a.right - r.left;
      const y1 = a.top - r.top + a.height / 2;
      const x2 = b.left - r.left;
      const y2 = b.top - r.top + b.height / 2;
      const dx = Math.max(60, (x2 - x1) / 2);
      setPath(
        `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
      );
    };
    compute();
    const ro = new ResizeObserver(compute);
    if (container.current) ro.observe(container.current);
    window.addEventListener("resize", compute);
    window.addEventListener("scroll", compute, true);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", compute);
      window.removeEventListener("scroll", compute, true);
    };
  }, [fromId, toId, active, container]);

  // Measure the true path length so stroke-dashoffset animates precisely.
  useEffect(() => {
    if (!pathRef.current || !path) return;
    setLength(pathRef.current.getTotalLength());
  }, [path]);

  if (!active || !path) return null;

  const animate = !reduced.current;

  return (
    <svg
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full"
      style={{ overflow: "visible" }}
    >
      <path
        ref={pathRef}
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1}
        strokeLinecap="round"
        style={
          animate && length
            ? {
                strokeDasharray: length,
                strokeDashoffset: length,
                animation: "thread-illuminate 400ms ease-out forwards",
              }
            : { opacity: 1 }
        }
        key={`${fromId}-${toId}-${status}`}
      />
      <circle cx={firstXY(path)[0]} cy={firstXY(path)[1]} r={2} fill={color} />
      <circle cx={lastXY(path)[0]} cy={lastXY(path)[1]} r={2} fill={color} />
    </svg>
  );
}

function firstXY(path: string): [number, number] {
  const m = path.match(/M ([\d.]+) ([\d.]+)/);
  return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 0];
}
function lastXY(path: string): [number, number] {
  const c = path.match(/,\s*([\d.]+)\s+([\d.]+)$/);
  return c ? [parseFloat(c[1]), parseFloat(c[2])] : [0, 0];
}
