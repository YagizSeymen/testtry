import { UserX, TrendingDown, Puzzle, ShieldAlert, type LucideIcon } from "lucide-react";
import type { Objection } from "@/lib/applications-data";
import { AgentRationale } from "./agent-rationale";
import { AGENT_ICON } from "./agent";

const severityColor = {
  red: "var(--contested-red)",
  yellow: "var(--contested-amber)",
  dim: "var(--dim)",
} as const;

const statusStyle = {
  verified: "var(--verified)",
  unverified: "var(--contested-amber)",
  "n/a": "var(--dim)",
} as const;

/** Map each persona to a distinct icon. Unknown personas fall back to a generic. */
const personaIcon: Record<string, LucideIcon> = {
  "Founder-Risk Partner": UserX,
  "Market-Skeptic Partner": TrendingDown,
  "Product-Market-Fit Skeptic": Puzzle,
};

/**
 * Adversarial objection card. Renders:
 *  - the persona as a display-font header with a persona icon (step 7)
 *  - the objection body wrapped by AgentRationale (Adversary Agent)
 *  - two orthogonal tags: evidence-backed/speculation, verified/unverified/n/a
 *  - a re-verification attribution line (Diligence Judge re-verifying)
 */
export function ObjectionCard({ objection }: { objection: Objection }) {
  const sev = severityColor[objection.severity];
  const PersonaIcon = personaIcon[objection.persona] ?? ShieldAlert;
  const JudgeIcon = AGENT_ICON["Diligence Judge (re-verifying)"];
  return (
    <article
      className="rounded-md bg-[var(--paper)] p-5 text-[var(--ink)]"
      style={{ borderLeft: `3px solid ${sev}` }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <PersonaIcon
            size={18}
            strokeWidth={1.75}
            aria-hidden
            style={{ color: sev }}
          />
          <h4 className="font-display text-lg font-medium tracking-tight text-[var(--ink)]">
            {objection.persona}
          </h4>
        </div>
        <span
          className="inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest"
          style={{
            background: `color-mix(in oklab, ${sev} 12%, transparent)`,
            color: sev,
            border: `1px solid color-mix(in oklab, ${sev} 40%, transparent)`,
          }}
        >
          <span aria-hidden className="h-1 w-1 rounded-full" style={{ background: sev }} />
          {objection.severity}
        </span>
      </div>

      <div className="mt-3">
        <AgentRationale agent="Adversary Agent" surface="paper">
          {objection.objection}
        </AgentRationale>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-[var(--ink)]/10 pt-3">
        <span
          className="rounded-sm border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest"
          style={{
            borderColor:
              objection.label === "evidence-backed"
                ? "color-mix(in oklab, var(--signal) 45%, transparent)"
                : "color-mix(in oklab, var(--ink) 30%, transparent)",
            color:
              objection.label === "evidence-backed" ? "var(--signal)" : "var(--ink)",
          }}
        >
          {objection.label}
        </span>
        <span
          className="inline-flex items-center gap-1.5 rounded-sm border bg-transparent px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest"
          style={{
            borderColor: `color-mix(in oklab, ${statusStyle[objection.status]} 45%, transparent)`,
            color: statusStyle[objection.status],
          }}
        >
          <span aria-hidden className="h-1 w-1 rounded-full" style={{ background: statusStyle[objection.status] }} />
          {objection.status}
        </span>
        {objection.claim_id && (
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
            ↔ {objection.claim_id}
          </span>
        )}
      </div>

      {/* Re-verification attribution — appears once status has resolved */}
      <div className="mt-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
        <JudgeIcon size={11} strokeWidth={1.75} aria-hidden />
        <span>
          re-verified by diligence judge —{" "}
          <span style={{ color: statusStyle[objection.status] }}>
            {objection.status}
          </span>
        </span>
      </div>
    </article>
  );
}
