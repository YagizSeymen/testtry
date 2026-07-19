import type { DecisionBrief as Brief } from "@/lib/applications-data";

const dotColor = {
  red: "var(--contested-red)",
  yellow: "var(--contested-amber)",
  dim: "var(--dim)",
} as const;

/**
 * Decision Brief — the case-file summary card. Never implies a "winner".
 * Renders the exact summary sentence verbatim in Space Grotesk, then lists
 * the contested (claim, objection) pairs as severity-colored chips.
 *
 * Surface: "paper" for use on the ink desk (dark background).
 * Surface: "ink" for use on paper (light) backgrounds.
 */
export function DecisionBriefCard({
  brief,
  surface = "paper",
}: {
  brief: Brief;
  surface?: "paper" | "ink";
}) {
  const isPaper = surface === "paper";
  const bg = isPaper ? "var(--paper)" : "var(--paper)/[0.04]";
  const fg = isPaper ? "var(--ink)" : "var(--paper)";
  const meta = isPaper ? "var(--ink)/60" : "var(--paper)/60";
  const rule = isPaper ? "var(--ink)/10" : "var(--paper)/12";

  return (
    <section
      className="rounded-md p-6"
      style={{
        background: isPaper ? "var(--paper)" : "color-mix(in oklab, var(--paper) 4%, transparent)",
        color: isPaper ? "var(--ink)" : "var(--paper)",
        border: isPaper ? "none" : `1px solid color-mix(in oklab, var(--paper) 10%, transparent)`,
      }}
    >
      <div
        className="font-mono text-[10px] uppercase tracking-widest"
        style={{ color: `color-mix(in oklab, ${fg} 55%, transparent)` }}
      >
        decision brief · case file
      </div>

      <h3
        className="mt-2 font-display text-[19px] font-medium leading-snug tracking-tight"
        style={{ color: fg }}
      >
        {brief.summary}
      </h3>

      {/* Severity totals */}
      <div className="mt-4 flex flex-wrap gap-2">
        <SeverityTotal count={brief.red} severity="red" surface={surface} />
        <SeverityTotal count={brief.yellow} severity="yellow" surface={surface} />
        <SeverityTotal count={brief.dim} severity="dim" surface={surface} />
      </div>

      {brief.contested_pairs.length > 0 && (
        <div
          className="mt-5 border-t pt-4"
          style={{ borderColor: `color-mix(in oklab, ${rule.replace('/[', ' ').replace(']', '')}, transparent)` }}
        >
          <div
            className="font-mono text-[10px] uppercase tracking-widest"
            style={{ color: `color-mix(in oklab, ${fg} 55%, transparent)` }}
          >
            contested pairs · claim ↔ objection
          </div>
          <ul className="mt-3 space-y-2">
            {brief.contested_pairs.map((p) => (
              <li key={p.id}>
                <div className="flex items-start gap-3">
                  <span
                    aria-hidden
                    className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                    style={{ background: dotColor[p.severity] }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {p.claim_id && (
                        <span
                          className="rounded-sm px-1.5 py-0.5 font-mono text-[10px]"
                          style={{
                            background: `color-mix(in oklab, ${dotColor[p.severity]} 15%, transparent)`,
                            color: dotColor[p.severity],
                            border: `1px solid color-mix(in oklab, ${dotColor[p.severity]} 40%, transparent)`,
                          }}
                        >
                          {p.claim_id}
                        </span>
                      )}
                      <span className="font-mono text-[10px]" style={{ color: `color-mix(in oklab, ${fg} 45%, transparent)` }}>
                        ↔
                      </span>
                      <span
                        className="rounded-sm px-1.5 py-0.5 font-mono text-[10px]"
                        style={{
                          background: `color-mix(in oklab, ${dotColor[p.severity]} 15%, transparent)`,
                          color: dotColor[p.severity],
                          border: `1px solid color-mix(in oklab, ${dotColor[p.severity]} 40%, transparent)`,
                        }}
                      >
                        {p.objection_id}
                      </span>
                    </div>
                    <div
                      className="mt-1 text-[13px] leading-snug"
                      style={{ color: `color-mix(in oklab, ${fg} 85%, transparent)` }}
                    >
                      {p.label}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        className="mt-5 border-t pt-3 font-mono text-[10px] uppercase tracking-widest"
        style={{
          borderColor: `color-mix(in oklab, ${fg} 10%, transparent)`,
          color: `color-mix(in oklab, ${fg} 45%, transparent)`,
        }}
      >
        this brief does not decide · a human clicks approve or reject
      </div>
    </section>
  );
}

function SeverityTotal({
  count,
  severity,
  surface,
}: {
  count: number;
  severity: "red" | "yellow" | "dim";
  surface: "paper" | "ink";
}) {
  const isPaper = surface === "paper";
  const c = dotColor[severity];
  const label = severity === "red" ? "red" : severity === "yellow" ? "yellow" : "dim";
  return (
    <div
      className="inline-flex items-center gap-2 rounded-sm px-2.5 py-1"
      style={{
        background: `color-mix(in oklab, ${c} 12%, transparent)`,
        border: `1px solid color-mix(in oklab, ${c} 35%, transparent)`,
      }}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />
      <span className="font-mono text-sm font-medium tabular-nums" style={{ color: c }}>
        {count}
      </span>
      <span
        className="font-mono text-[10px] uppercase tracking-widest"
        style={{
          color: isPaper
            ? "color-mix(in oklab, var(--ink) 55%, transparent)"
            : "color-mix(in oklab, var(--paper) 55%, transparent)",
        }}
      >
        {label}
      </span>
    </div>
  );
}
