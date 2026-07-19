import type { ReactNode } from "react";
import { AGENT_ICON, type AgentName } from "./agent";

/**
 * Agent Rationale Block — wraps any AI-generated text with an eyebrow
 * label naming the agent that produced it. Reuses the dashed visual
 * language established by the "synthetic" chips + "no exact quote" tag.
 *
 * Surface: "paper" (default, for use on paper-colored cards) or "ink"
 * (for use directly on the dark ink surface).
 */
export function AgentRationale({
  agent,
  children,
  surface = "paper",
  className = "",
}: {
  agent: AgentName;
  children: ReactNode;
  surface?: "paper" | "ink";
  className?: string;
}) {
  const Icon = AGENT_ICON[agent];
  const onInk = surface === "ink";
  const borderColor = onInk
    ? "color-mix(in oklab, var(--paper) 25%, transparent)"
    : "color-mix(in oklab, var(--ink) 18%, transparent)";
  const eyebrowColor = onInk ? "text-[var(--paper)]/60" : "text-[var(--ink)]/55";
  const bodyColor = onInk ? "text-[var(--paper)]/88" : "text-[var(--ink)]/80";
  const bg = onInk
    ? "bg-[color-mix(in_oklab,var(--ink)_82%,transparent)]"
    : "bg-[color-mix(in_oklab,var(--ink)_5%,transparent)]";
  return (
    <div
      className={`rounded-sm border border-dashed ${bg} px-3 py-2.5 ${className}`}
      style={{ borderColor }}
    >
      <div
        className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest ${eyebrowColor}`}
      >
        <Icon size={11} strokeWidth={1.75} aria-hidden />
        <span>{agent.toLowerCase()}</span>
      </div>
      <div className={`mt-1.5 text-[13px] leading-relaxed ${bodyColor}`}>
        {children}
      </div>
    </div>
  );
}
