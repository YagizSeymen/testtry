import { AGENT_ICON, type AgentName } from "./agent";

/**
 * Working state: replaces generic spinners with a small agent icon + label.
 * No streaming, no typewriter — a single static "in progress" state.
 */
export function AgentWorking({
  agent,
  className = "",
  surface = "ink",
}: {
  agent: AgentName;
  className?: string;
  surface?: "paper" | "ink";
}) {
  const Icon = AGENT_ICON[agent];
  const onInk = surface === "ink";
  const color = onInk ? "text-[var(--paper)]/70" : "text-[var(--ink)]/70";
  return (
    <span
      className={`inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest ${color} ${className}`}
    >
      <Icon
        size={13}
        strokeWidth={1.75}
        aria-hidden
        className="animate-pulse"
        style={{ color: "var(--signal)" }}
      />
      <span>{agent.toLowerCase()} is working…</span>
    </span>
  );
}
