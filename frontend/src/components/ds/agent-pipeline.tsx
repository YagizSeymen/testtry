import type { StageState } from "@/lib/applications-data";

export type PipelineStageKey =
  | "extractor"
  | "screen"
  | "diligence"
  | "memo"
  | "adversary"
  | "verify";

export type PipelineStage = {
  key: PipelineStageKey;
  label: string;
  state: StageState | "running";
  /** color used for "complete" fill — reuses tokens already in the palette */
  color: string;
};

/**
 * Horizontal 6-node pipeline strip visualising which agent has run.
 * - hollow/dim   = not_run
 * - pulsing      = running (reuses tw-animate-css's pulse)
 * - filled       = complete (uses per-stage severity/trust color)
 * Sits above the tabs; does not replace them.
 */
export function AgentPipeline({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="w-full">
      <div className="flex items-center gap-1.5">
        {stages.map((s, i) => (
          <div key={s.key} className="flex flex-1 items-center gap-1.5">
            <PipelineNode stage={s} />
            {i < stages.length - 1 && (
              <span
                aria-hidden
                className="h-px flex-1"
                style={{
                  background:
                    "color-mix(in oklab, var(--ink) 15%, transparent)",
                }}
              />
            )}
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-1.5">
        {stages.map((s, i) => (
          <div key={s.key} className="flex flex-1 items-center gap-1.5">
            <div className="w-3.5" />
            <span
              className={
                "flex-1 font-mono text-[10px] uppercase tracking-widest " +
                (s.state === "complete"
                  ? "text-[var(--ink)]/75"
                  : s.state === "running"
                    ? "text-[var(--signal)]"
                    : "text-[var(--ink)]/40")
              }
            >
              {s.label}
            </span>
            {i < stages.length - 1 && <span className="flex-1" />}
          </div>
        ))}
      </div>
    </div>
  );
}

function PipelineNode({ stage }: { stage: PipelineStage }) {
  const complete = stage.state === "complete";
  const running = stage.state === "running";
  return (
    <span
      aria-label={`${stage.label} · ${stage.state}`}
      className={
        "relative inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full transition-colors " +
        (running ? "animate-pulse" : "")
      }
      style={{
        background: complete ? stage.color : "transparent",
        borderStyle: "solid",
        borderWidth: 1,
        borderColor: complete
          ? stage.color
          : running
            ? "var(--signal)"
            : "color-mix(in oklab, var(--ink) 22%, transparent)",
        boxShadow: complete
          ? `0 0 0 2px color-mix(in oklab, ${stage.color} 22%, transparent)`
          : running
            ? `0 0 0 2px color-mix(in oklab, var(--signal) 22%, transparent)`
            : "none",
      }}
    />
  );
}
