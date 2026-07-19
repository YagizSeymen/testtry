import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { DecisionBriefCard } from "@/components/ds";
import { AuditDrawer } from "@/components/audit-drawer";
import type { DecisionBrief, DecisionState } from "@/lib/applications-data";

export const Route = createFileRoute("/queue")({
  component: QueuePage,
});

type QueueItem = {
  id: string;
  company: string;
  founder_name: string;
  founder_id: string;
  submitted_at: string;
  recommendation: {
    verdict: "invest" | "pass" | "revisit";
    amount_usd: number | null;
    one_liner: string;
  };
  brief: DecisionBrief | null;
  decision: DecisionState;
};

type Metrics = {
  signal_to_decision_min: number;
  funnel: { sourced: number; screened: number; diligenced: number; decided: number };
};

function QueuePage() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [audit, setAudit] = useState<{ appId?: string; title?: string } | null>(null);

  const loadQueue = useCallback(async () => {
    const res = await fetch("/api/decisions/queue");
    const d: { queue: QueueItem[] } = await res.json();
    setItems(d.queue);
  }, []);

  useEffect(() => {
    loadQueue();
    fetch("/api/metrics")
      .then((r) => r.json())
      .then(setMetrics);
  }, [loadQueue]);

  async function submitDecision(id: string, verdict: "approved" | "rejected") {
    setDeciding(id);
    try {
      await fetch(`/api/decisions/${id}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verdict }),
      });
      await loadQueue();
    } finally {
      setDeciding(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 md:px-10 md:py-12">
      <div className="fancy-card gradient-border rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-hero)] p-6 shadow-[0_32px_80px_-64px_rgba(24,33,70,0.7)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
              decision queue
            </div>
            <h1 className="mt-1 font-display text-3xl font-medium tracking-tight">
              Human gate
            </h1>
            <p className="mt-2 max-w-xl text-sm text-[var(--ink)]/60">
              Every application that clears the memo lands here. The brief tells you
              what is contested. You still click approve or reject.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatPill label="queue" value={`${items?.length ?? "…"} pending`} tone="signal" />
            <StatPill
              label="decision median"
              value={metrics ? `${metrics.signal_to_decision_min} min` : "—"}
              tone="verified"
            />
            <button
              type="button"
              onClick={() => setAudit({ appId: undefined, title: "All applications" })}
              className="shrink-0 rounded-sm border border-[var(--ink)]/20 px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/80 transition-colors hover:border-[var(--ink)]/45 hover:text-[var(--ink)]"
            >
              Open audit log
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-5 shadow-[0_20px_55px_-50px_rgba(24,33,70,0.6)]">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
              compliance posture
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <MiniMetric label="sourced" value={metrics?.funnel.sourced ?? "—"} tone="signal" />
              <MiniMetric label="screened" value={metrics?.funnel.screened ?? "—"} tone="verified" />
              <MiniMetric label="diligenced" value={metrics?.funnel.diligenced ?? "—"} tone="amber" />
              <MiniMetric label="decided" value={metrics?.funnel.decided ?? "—"} tone="verified" />
              <MiniMetric
                label="open"
                value={items?.length ?? "—"}
                tone={(items?.length ?? 0) > 0 ? "red" : "dim"}
              />
            </div>
          </div>
          <div className="rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-5 shadow-[0_18px_48px_-50px_rgba(24,33,70,0.55)]">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
              decision guardrails
            </div>
            <ul className="mt-3 space-y-2 text-[13px] text-[var(--ink)]/75">
              <li className="flex items-center gap-2">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--signal)]" />
                Memo + adversary are required before a decision.
              </li>
              <li className="flex items-center gap-2">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--contested-amber)]" />
                Contested pairs stay visible on every case file.
              </li>
              <li className="flex items-center gap-2">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--verified)]" />
                Audit trail is immutable and export-ready.
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Queue */}
      <section className="mt-10">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="font-display text-lg font-medium tracking-tight text-[var(--ink)]/90">
            Pending decisions
          </h2>
          <span className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
            {items?.length ?? "…"} in queue
          </span>
        </div>

        {items === null ? (
          <div className="h-40 animate-pulse rounded-md bg-[var(--ink)]/[0.06]" />
        ) : items.length === 0 ? (
          <div className="rounded-md border border-dashed border-[var(--ink)]/20 bg-[var(--paper)] p-10 text-center">
            <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
              queue is empty
            </div>
            <h3 className="mt-2 font-display text-xl font-medium tracking-tight text-[var(--ink)]/90">
              Nothing waiting on a human right now.
            </h3>
            <p className="mt-2 text-sm text-[var(--ink)]/55">
              Applications land here once their memo is drafted. The queue does
              not decide anything on its own.
            </p>
          </div>
        ) : (
          <ul className="space-y-6">
            {items.map((it) => (
              <li key={it.id}>
                <QueueRow
                  item={it}
                  deciding={deciding === it.id}
                  onDecide={(v) => submitDecision(it.id, v)}
                  onOpenAudit={() =>
                    setAudit({ appId: it.id, title: `${it.company} · ${it.id}` })
                  }
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <AuditDrawer
        open={audit !== null}
        onClose={() => setAudit(null)}
        applicationId={audit?.appId}
        title={audit?.title}
      />
    </div>
  );
}

const VERDICT_COLOR: Record<QueueItem["recommendation"]["verdict"], string> = {
  invest: "var(--verified)",
  pass: "var(--contested-red)",
  revisit: "var(--contested-amber)",
};

function QueueRow({
  item,
  deciding,
  onDecide,
  onOpenAudit,
}: {
  item: QueueItem;
  deciding: boolean;
  onDecide: (verdict: "approved" | "rejected") => void;
  onOpenAudit: () => void;
}) {
  const isDecided = item.decision === "approved" || item.decision === "rejected";
  const verdictColor = VERDICT_COLOR[item.recommendation.verdict];

  return (
    <article className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_24px_60px_-50px_rgba(24,33,70,0.65)] md:p-7">
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Left: identity + rec */}
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <Link
              to="/application/$id"
              params={{ id: item.id }}
              className="font-display text-2xl font-medium tracking-tight text-[var(--ink)] hover:underline"
            >
              {item.company}
            </Link>
            <Link
              to="/founder/$id"
              params={{ id: item.founder_id }}
              className="font-mono text-[11px] uppercase tracking-widest text-[var(--signal)] underline underline-offset-4"
            >
              {item.founder_name}
            </Link>
          </div>
          <div className="mt-1 font-mono text-[11px] text-[var(--ink)]/55">
            app · {item.id} · submitted{" "}
            {new Date(item.submitted_at).toISOString().slice(0, 10)}
          </div>

          <div className="mt-5 rounded-2xl border border-[var(--ink)]/10 bg-[var(--paper)]/70 p-4">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
              recommendation
            </div>
            <div className="mt-1 flex flex-wrap items-baseline gap-3">
              <span
                className="font-display text-xl font-medium uppercase tracking-tight"
                style={{ color: verdictColor }}
              >
                {item.recommendation.verdict}
              </span>
              {item.recommendation.amount_usd != null && (
                <span className="font-mono text-base text-[var(--ink)]/85">
                  ${item.recommendation.amount_usd.toLocaleString()}
                </span>
              )}
            </div>
            <p className="mt-2 max-w-[52ch] text-[14px] leading-relaxed text-[var(--ink)]/80">
              {item.recommendation.one_liner}
            </p>
            <div className="mt-4 border-t border-[var(--ink)]/10 pt-3">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
                risk heat
              </div>
              <RiskHeatChips brief={item.brief} />
            </div>
          </div>

          {/* Decision + secondary actions */}
          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[var(--ink)]/10 pt-5">
            {isDecided ? (
              <DecisionBadge decision={item.decision} />
            ) : (
              <>
                <button
                  type="button"
                  disabled={deciding}
                  onClick={() => onDecide("approved")}
                  className="inline-flex items-center gap-2 rounded-sm px-4 py-2.5 font-display text-sm font-medium tracking-tight text-[var(--paper)] transition-colors disabled:opacity-50"
                  style={{ background: "var(--verified)" }}
                >
                  <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--paper)]" />
                  Approve
                </button>
                <button
                  type="button"
                  disabled={deciding}
                  onClick={() => onDecide("rejected")}
                  className="inline-flex items-center gap-2 rounded-sm border-2 px-4 py-2 font-display text-sm font-medium tracking-tight transition-colors disabled:opacity-50"
                  style={{
                    borderColor: "var(--contested-red)",
                    color: "var(--contested-red)",
                  }}
                >
                  Reject
                </button>
              </>
            )}
            <div className="ml-auto flex items-center gap-3">
              <Link
                to="/application/$id"
                params={{ id: item.id }}
                className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/60 underline underline-offset-4 hover:text-[var(--ink)]"
              >
                open memo
              </Link>
              <button
                type="button"
                onClick={onOpenAudit}
                className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/60 underline underline-offset-4 hover:text-[var(--ink)]"
              >
                audit trail
              </button>
            </div>
          </div>
        </div>

        {/* Right: brief */}
        <div>
          {item.brief ? (
            <DecisionBriefCard brief={item.brief} surface="paper" />
          ) : (
            <div className="rounded-2xl border border-dashed border-[var(--ink)]/25 bg-[var(--ink)]/[0.03] p-5">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
                decision brief · not yet run
              </div>
              <p className="mt-2 text-sm text-[var(--ink)]/70">
                Devil's Advocate hasn't run for this application yet. Open the
                application and click{" "}
                <span className="font-mono text-[var(--ink)]/85">
                  Run Devil's Advocate
                </span>{" "}
                to generate the brief.
              </p>
              <Link
                to="/application/$id"
                params={{ id: item.id }}
                className="mt-3 inline-flex items-center gap-2 rounded-sm border border-[var(--ink)]/25 px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/80 hover:border-[var(--ink)]/50"
              >
                open application →
              </Link>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function StatPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "signal" | "verified" | "amber" | "red" | "dim" | "ink";
}) {
  const toneColor = {
    signal: "var(--signal)",
    verified: "var(--verified)",
    amber: "var(--contested-amber)",
    red: "var(--contested-red)",
    dim: "var(--dim)",
    ink: "var(--ink)",
  }[tone];
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest"
      style={{
        borderColor: `color-mix(in oklab, ${toneColor} 28%, transparent)`,
        color: `color-mix(in oklab, ${toneColor} 75%, var(--ink))`,
        background: `color-mix(in oklab, ${toneColor} 10%, transparent)`,
      }}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: toneColor }} />
      <span>{label}</span>
      <span className="font-sans text-[12px] font-semibold normal-case text-[var(--ink)]">
        {value}
      </span>
    </div>
  );
}

function MiniMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone: "verified" | "amber" | "red" | "dim" | "signal" | "ink";
}) {
  const toneColor = {
    verified: "var(--verified)",
    amber: "var(--contested-amber)",
    red: "var(--contested-red)",
    dim: "var(--dim)",
    signal: "var(--signal)",
    ink: "var(--ink)",
  }[tone];
  return (
    <div className="rounded-2xl border border-[var(--ink)]/10 bg-[var(--paper)]/60 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
        {label}
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: toneColor }} />
        <span className="font-display text-lg font-semibold tracking-tight" style={{ color: toneColor }}>
          {value}
        </span>
      </div>
    </div>
  );
}

function DecisionBadge({ decision }: { decision: DecisionState }) {
  const label = decision ?? "pending";
  const tone =
    decision === "approved"
      ? "var(--verified)"
      : decision === "rejected"
        ? "var(--contested-red)"
        : decision === "pending" || decision == null
          ? "var(--dim)"
          : "var(--contested-amber)";
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border px-3 py-2 font-mono text-[11px] uppercase tracking-widest"
      style={{
        borderColor: `color-mix(in oklab, ${tone} 32%, transparent)`,
        background: `color-mix(in oklab, ${tone} 12%, transparent)`,
        color: tone,
      }}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: tone }} />
      decided · {label}
    </div>
  );
}

function RiskHeatChips({ brief }: { brief: DecisionBrief | null }) {
  if (!brief) {
    return (
      <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-[var(--ink)]/15 px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--dim)]" />
        brief pending
      </div>
    );
  }
  const chips = [
    { label: "red", value: brief.red, color: "var(--contested-red)" },
    { label: "yellow", value: brief.yellow, color: "var(--contested-amber)" },
    { label: "dim", value: brief.dim, color: "var(--dim)" },
  ];
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      {chips.map((c) => (
        <span
          key={c.label}
          className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest"
          style={{
            borderColor: `color-mix(in oklab, ${c.color} 40%, transparent)`,
            background: `color-mix(in oklab, ${c.color} 14%, transparent)`,
            color: c.color,
          }}
        >
          <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: c.color }} />
          {c.label}
          <span className="font-sans text-[11px] font-semibold normal-case text-[var(--ink)]">
            {c.value}
          </span>
        </span>
      ))}
    </div>
  );
}
