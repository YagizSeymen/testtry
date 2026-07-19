import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AgentPipeline,
  AgentRationale,
  AgentWorking,
  AGENT_ICON,
  DecisionBriefCard,
  EvidenceThread,
  ObjectionCard,
  TrendArrow,
  TrustBadge,
  type PipelineStage,
} from "@/components/ds";
import type { TrustLevel } from "@/components/ds";
import { AuditDrawer } from "@/components/audit-drawer";
import type {
  Adversary,
  Application,
  AxisCard,
  AxisVerdict,
  Claim,
  ClaimTrust,
  ClaimType,
  ClaimVerdict,
  DecisionState,
  DiligenceGap,
  DiligenceSignal,
  Memo,
  StageState,
} from "@/lib/applications-data";

export const Route = createFileRoute("/application/$id")({
  component: ApplicationPage,
});

type TabKey = "claims" | "screen" | "diligence" | "memo" | "adversary";
const TABS: Array<{ key: TabKey; label: string; stageKey: keyof Application["stage"] }> = [
  { key: "claims", label: "Claims", stageKey: "claims" },
  { key: "screen", label: "Screen", stageKey: "screen" },
  { key: "diligence", label: "Diligence", stageKey: "diligence" },
  { key: "memo", label: "Memo", stageKey: "memo" },
  { key: "adversary", label: "Devil's advocate", stageKey: "adversary" },
];

/** Build the 6-node pipeline strip: Extractor · Screen · Diligence · Memo · Adversary · Verify.
 *  Verify is a synthetic node — it turns green once the adversarial pass has
 *  resolved every objection to verified/unverified/n/a (i.e. adversary complete). */
function pipelineStages(app: Application, runningAdv: boolean): PipelineStage[] {
  const map = (s: StageState): "complete" | "not_run" =>
    s === "complete" ? "complete" : "not_run";
  const advState: PipelineStage["state"] = runningAdv
    ? "running"
    : map(app.stage.adversary);
  const verifyState: PipelineStage["state"] =
    app.adversary && app.stage.adversary === "complete" ? "complete" : "not_run";
  return [
    { key: "extractor", label: "Extractor", state: map(app.stage.claims), color: "var(--signal)" },
    { key: "screen", label: "Screen", state: map(app.stage.screen), color: "var(--verified)" },
    { key: "diligence", label: "Diligence", state: map(app.stage.diligence), color: "var(--contested-amber)" },
    { key: "memo", label: "Memo", state: map(app.stage.memo), color: "var(--signal)" },
    { key: "adversary", label: "Adversary", state: advState, color: "var(--contested-red)" },
    { key: "verify", label: "Verify", state: verifyState, color: "var(--verified)" },
  ];
}

function ApplicationPage() {
  const { id } = Route.useParams();
  const [app, setApp] = useState<Application | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<TabKey>("claims");
  const [auditOpen, setAuditOpen] = useState(false);
  const [runningAdversary, setRunningAdversary] = useState(false);
  const [compact, setCompact] = useState(false);
  const trustSummary = useMemo(() => {
    const base = {
      high: 0,
      med: 0,
      low: 0,
      contradicted: 0,
      unset: 0,
    };
    for (const c of app?.claims ?? []) {
      if (!c.trust) {
        base.unset += 1;
      } else {
        base[c.trust] += 1;
      }
    }
    return base;
  }, [app?.claims]);
  const stageSummary = useMemo(() => {
    const stages = app?.stage ? Object.values(app.stage) : [];
    const complete = stages.filter((s) => s === "complete").length;
    return { complete, total: stages.length || 5 };
  }, [app?.stage]);

  const loadApp = useCallback(async () => {
    const r = await fetch(`/api/applications/${id}`);
    if (r.status === 404) {
      setNotFound(true);
      return;
    }
    const d: Application = await r.json();
    setApp(d);
  }, [id]);

  useEffect(() => {
    setApp(null);
    setNotFound(false);
    loadApp();
  }, [loadApp]);

  async function runAdversary() {
    setRunningAdversary(true);
    try {
      const r = await fetch(`/api/applications/${id}/adversary`, { method: "POST" });
      if (r.ok) {
        const d: Application = await r.json();
        setApp(d);
        setTab("adversary");
      }
    } finally {
      setRunningAdversary(false);
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 sm:px-6 md:px-10">
        <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
          not found
        </div>
        <h1 className="mt-1 font-display text-2xl font-medium tracking-tight">
          No application with id{" "}
          <span className="font-mono text-[var(--ink)]/80">{id}</span>
        </h1>
        <Link
          to="/application"
          className="mt-4 inline-block font-mono text-[11px] uppercase tracking-widest text-[var(--signal)] underline underline-offset-4"
        >
          back to applications
        </Link>
      </div>
    );
  }

  if (!app) {
    return (
      <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 md:px-10 md:py-12">
        <div className="h-6 w-40 animate-pulse rounded bg-[var(--paper)]/10" />
        <div className="mt-3 h-9 w-96 animate-pulse rounded bg-[var(--paper)]/10" />
        <div className="mt-8 h-40 animate-pulse rounded-md bg-[var(--ink)]/[0.06]" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-6 md:px-10 md:py-12">
      <Link
        to="/application"
        className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/50 hover:text-[var(--ink)]/90"
      >
        ← all applications
      </Link>

      {/* Header */}
      <header className="mt-4">
        <div className="fancy-card gradient-border rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-hero)] p-6 shadow-[0_32px_80px_-64px_rgba(24,33,70,0.7)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <h1 className="font-display text-4xl font-medium tracking-tight text-[var(--ink)]">
                  {app.company}
                </h1>
                <Link
                  to="/founder/$id"
                  params={{ id: app.founder_id }}
                  className="font-mono text-[12px] uppercase tracking-widest text-[var(--signal)] underline underline-offset-4"
                >
                  {app.founder_name}
                </Link>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-[var(--ink)]/55">
                <span>app · {app.id}</span>
                <span>·</span>
                <span>submitted {new Date(app.submitted_at).toISOString().slice(0, 10)}</span>
                <span>·</span>
                <span>{app.deck_pages} slides</span>
                <span>·</span>
                <span>{app.claims.length} claims extracted</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {app.memo && app.stage.adversary === "not_run" && (
                <button
                  type="button"
                  onClick={runAdversary}
                  disabled={runningAdversary}
                  className="inline-flex items-center gap-2 rounded-sm px-3 py-2 font-display text-sm font-medium tracking-tight text-[var(--paper)] transition-colors disabled:opacity-50"
                  style={{ background: "var(--contested-red)" }}
                >
                  {runningAdversary ? (
                    <AgentWorking agent="Adversary Agent" surface="ink" />
                  ) : (
                    <>
                      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--paper)]" />
                      Run Devil's Advocate
                    </>
                  )}
                </button>
              )}
              <button
                type="button"
                onClick={() => setAuditOpen(true)}
                className="rounded-sm border border-[var(--ink)]/20 px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/80 hover:border-[var(--ink)]/45 hover:text-[var(--ink)]"
              >
                audit trail
              </button>
              <button
                type="button"
                onClick={() => setCompact((v) => !v)}
                className="rounded-full border border-[var(--ink)]/15 bg-white/70 px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/70 shadow-[0_10px_24px_-20px_rgba(27,37,94,0.45)] hover:text-[var(--ink)]"
              >
                {compact ? "Comfortable view" : "Compact view"}
              </button>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <StatPill label="stage" value={`${stageSummary.complete}/${stageSummary.total} complete`} tone="signal" />
            <StatPill label="claims" value={String(app.claims.length)} tone="ink" />
            <StatPill
              label="signals"
              value={String(app.diligence?.signals.length ?? 0)}
              tone="verified"
            />
            <StatPill
              label="gaps"
              value={String(app.diligence?.gaps.length ?? 0)}
              tone="amber"
            />
            <DecisionPill decision={app.decision} />
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-5 shadow-[0_22px_56px_-50px_rgba(24,33,70,0.6)]">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
              evidence ledger · compliance summary
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <MiniMetric label="verified" value={trustSummary.high} tone="verified" />
              <MiniMetric label="mixed" value={trustSummary.med} tone="amber" />
              <MiniMetric label="unverifiable" value={trustSummary.low} tone="dim" />
              <MiniMetric label="contradicted" value={trustSummary.contradicted} tone="red" />
              <MiniMetric label="unset" value={trustSummary.unset} tone="ink" />
            </div>
            <div className="mt-4 border-t border-[var(--ink)]/10 pt-3 text-[12px] text-[var(--ink)]/70">
              Every claim is tied back to a source span or a flagged gap. Contradictions
              surface in-line with the signal that broke them.
            </div>
          </div>
          <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-5 shadow-[0_20px_48px_-50px_rgba(24,33,70,0.6)]">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
              decision posture
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <DecisionBadge decision={app.decision} />
              <div className="font-mono text-[11px] text-[var(--ink)]/60">
                last updated {new Date(app.submitted_at).toISOString().slice(0, 10)}
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <MiniMetric label="memo" value={app.stage.memo === "complete" ? "ready" : "pending"} tone="signal" />
              <MiniMetric
                label="adversary"
                value={app.stage.adversary === "complete" ? "cleared" : "not run"}
                tone={app.stage.adversary === "complete" ? "verified" : "red"}
              />
            </div>
            <div className="mt-4 border-t border-[var(--ink)]/10 pt-3 text-[12px] text-[var(--ink)]/70">
              Decision never auto-resolves. A human gate approves or rejects after audit review.
            </div>
          </div>
        </div>
      </header>

      {/* Agent Pipeline strip — one node per agent, above the tabs */}
      <section className="mt-6" aria-label="Agent pipeline">
        <AgentPipeline stages={pipelineStages(app, runningAdversary)} />
      </section>

      {/* Tab stepper */}
      <nav
        className="mt-6 flex flex-wrap gap-2"
        aria-label="Application stages"
      >
        {TABS.map((t, i) => (
          <TabButton
            key={t.key}
            index={i}
            label={t.label}
            state={app.stage[t.stageKey]}
            active={tab === t.key}
            onClick={() => setTab(t.key)}
          />
        ))}
      </nav>

      {/* Tab body */}
      <div className={compact ? "mt-8 density-compact" : "mt-8"}>
        {tab === "claims" && <ClaimsTab claims={app.claims} state={app.stage.claims} />}
        {tab === "screen" && <ScreenTab screen={app.screen} state={app.stage.screen} onRun={() => setTab("claims")} />}
        {tab === "diligence" && (
          <DiligenceTab
            claims={app.claims}
            diligence={app.diligence}
            state={app.stage.diligence}
          />
        )}
        {tab === "memo" && (
          <MemoTab
            memo={app.memo}
            claims={app.claims}
            state={app.stage.memo}
            onJumpToClaim={() => setTab("diligence")}
          />
        )}
        {tab === "adversary" && (
          <AdversaryTab
            adversary={app.adversary}
            state={app.stage.adversary}
            memoReady={app.memo != null}
            running={runningAdversary}
            onRun={runAdversary}
          />
        )}
      </div>

      <AuditDrawer
        open={auditOpen}
        onClose={() => setAuditOpen(false)}
        applicationId={app.id}
        title={`${app.company} · ${app.id}`}
      />
    </div>
  );
}

// ─── Tab button with status dot ──────────────────────────────────────────────
function TabButton({
  index,
  label,
  state,
  active,
  onClick,
}: {
  index: number;
  label: string;
  state: StageState;
  active: boolean;
  onClick: () => void;
}) {
  const dotColor = state === "complete" ? "var(--verified)" : "var(--dim)";
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "relative flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors " +
        (active
          ? "border-[var(--signal)]/35 bg-[var(--surface-accent)] text-[var(--signal)]"
          : "border-[var(--ink)]/10 text-[var(--ink)]/60 hover:border-[var(--ink)]/20 hover:text-[var(--ink)]")
      }
    >
      <span
        aria-hidden
        className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45"
      >
        {String(index + 1).padStart(2, "0")}
      </span>
      <span className="font-display tracking-tight">{label}</span>
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full"
        style={{
          background: dotColor,
          boxShadow: state === "complete" ? `0 0 0 2px color-mix(in oklab, ${dotColor} 25%, transparent)` : "none",
          opacity: state === "complete" ? 1 : 0.55,
        }}
      />
    </button>
  );
}

// ─── Null state prompt ───────────────────────────────────────────────────────
function StageNotYetRun({
  stage,
  description,
  ctaLabel,
  onRun,
}: {
  stage: string;
  description: string;
  ctaLabel: string;
  onRun?: () => void;
}) {
  return (
    <div className="fancy-card rounded-3xl border border-dashed border-[var(--ink)]/20 bg-[var(--surface-card-soft)] p-8">
      <div className="flex items-start gap-5">
        <div
          aria-hidden
          className="mt-1 h-10 w-10 shrink-0 rounded-sm border border-[var(--ink)]/15"
          style={{
            backgroundImage:
              "repeating-linear-gradient(45deg, transparent 0 4px, color-mix(in oklab, var(--ink) 8%, transparent) 4px 5px)",
          }}
        />
        <div className="flex-1">
          <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
            stage · not yet run
          </div>
          <h3 className="mt-1 font-display text-xl font-medium tracking-tight text-[var(--ink)]">
            {stage}
          </h3>
          <p className="mt-2 max-w-[60ch] text-sm text-[var(--ink)]/65">{description}</p>
          <button
            type="button"
            onClick={onRun}
            className="mt-5 inline-flex items-center gap-2 rounded-sm bg-[var(--signal)] px-4 py-2 text-sm font-medium text-[var(--paper)] transition-colors hover:bg-[color-mix(in_oklab,var(--signal)_88%,white)]"
          >
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--paper)]" />
            {ctaLabel}
          </button>
        </div>
      </div>
    </div>
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

function DecisionPill({ decision }: { decision: DecisionState }) {
  if (!decision) {
    return <StatPill label="decision" value="pending" tone="dim" />;
  }
  return (
    <StatPill
      label="decision"
      value={decision}
      tone={decision === "approved" ? "verified" : decision === "rejected" ? "red" : "amber"}
    />
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
      className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest"
      style={{
        borderColor: `color-mix(in oklab, ${tone} 32%, transparent)`,
        background: `color-mix(in oklab, ${tone} 12%, transparent)`,
        color: tone,
      }}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: tone }} />
      {label}
    </div>
  );
}

// ─── Claim type badge ────────────────────────────────────────────────────────
const TYPE_STYLES: Record<ClaimType, string> = {
  traction: "bg-[color-mix(in_oklab,var(--signal)_18%,transparent)] text-[var(--signal)] ring-[color-mix(in_oklab,var(--signal)_40%,transparent)]",
  team: "bg-[color-mix(in_oklab,var(--verified)_18%,transparent)] text-[var(--verified)] ring-[color-mix(in_oklab,var(--verified)_40%,transparent)]",
  market: "bg-[color-mix(in_oklab,var(--contested-amber)_18%,transparent)] text-[var(--contested-amber)] ring-[color-mix(in_oklab,var(--contested-amber)_40%,transparent)]",
  product: "bg-[color-mix(in_oklab,var(--dim)_18%,transparent)] text-[var(--ink)]/85 ring-[color-mix(in_oklab,var(--dim)_40%,transparent)]",
};

function TypeBadge({ type }: { type: ClaimType }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ring-1 ring-inset " +
        TYPE_STYLES[type]
      }
    >
      {type}
    </span>
  );
}

// ─── Claims tab ──────────────────────────────────────────────────────────────
function ClaimsTab({ claims, state }: { claims: Claim[]; state: StageState }) {
  if (state === "not_run") {
    return (
      <StageNotYetRun
        stage="Extract claims"
        description="Run the extractor on the uploaded deck. Each claim will be quoted verbatim from its slide, tagged by type, and marked when no exact source span is available."
        ctaLabel="Run claim extractor"
      />
    );
  }
  return (
    <section>
      <SectionHead
        eyebrow="stage 01"
        title="Extracted claims"
        subtitle={`${claims.length} claims · quoted verbatim from the deck · null spans surfaced explicitly`}
      />
      <ul className="mt-6 space-y-4">
        {claims.map((c) => (
          <li key={c.id}>
            <ClaimRow claim={c} showTrust={false} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ClaimRow({
  claim,
  showTrust,
  idPrefix,
}: {
  claim: Claim;
  showTrust: boolean;
  idPrefix?: string;
}) {
  const domId = idPrefix ? `${idPrefix}-${claim.id}` : undefined;
  const borderColor: Record<ClaimTrust, string> = {
    high: "var(--verified)",
    med: "var(--contested-amber)",
    low: "var(--dim)",
    contradicted: "var(--contested-red)",
  };
  const leftBorder =
    showTrust && claim.trust ? borderColor[claim.trust] : "transparent";

  return (
    <article
      id={domId}
      className="fancy-card gradient-border glow-card rounded-2xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-5 text-[var(--ink)] shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)] md:p-6"
      style={{ borderLeft: `3px solid ${leftBorder}` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
            {claim.id}
          </span>
          <TypeBadge type={claim.type} />
        </div>
        {showTrust && claim.trust && (
          <div className="flex items-center gap-2">
            <TrustBadge level={claim.trust} />
            {claim.verdict && <VerdictTag verdict={claim.verdict} />}
          </div>
        )}
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--ink)]">
        {claim.text}
      </p>
      <div className="mt-4">
        {claim.source_span ? (
          <SourceSpan location={claim.source_span.location} quote={claim.source_span.quote} />
        ) : (
          <NoSpanTag />
        )}
      </div>
    </article>
  );
}

function SourceSpan({ location, quote }: { location: string; quote: string }) {
  return (
    <div className="relative rounded-sm border-l-2 border-[var(--ink)]/25 bg-[color-mix(in_oklab,var(--contested-amber)_10%,transparent)] px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
        source · {location}
      </div>
      <blockquote className="mt-1 font-mono text-[13px] leading-relaxed text-[var(--ink)]/85">
        &ldquo;{quote}&rdquo;
      </blockquote>
    </div>
  );
}

function NoSpanTag() {
  return (
    <div className="inline-flex items-center gap-2 rounded-sm border border-dashed border-[var(--ink)]/25 bg-[var(--ink)]/[0.03] px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/60">
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--ink)]/40" />
      no exact quote found · claim inferred
    </div>
  );
}

function VerdictTag({ verdict }: { verdict: ClaimVerdict }) {
  const styles: Record<ClaimVerdict, string> = {
    supported:
      "border-[var(--verified)]/50 text-[var(--verified)]",
    contradicted:
      "border-[var(--contested-red)]/60 text-[var(--contested-red)]",
    unverifiable: "border-[var(--dim)]/60 text-[var(--dim)]",
  };
  return (
    <span
      className={
        "inline-flex items-center rounded-sm border bg-transparent px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest " +
        styles[verdict]
      }
    >
      {verdict}
    </span>
  );
}

// ─── Screen tab: three axes, side by side, NEVER averaged ────────────────────
function ScreenTab({
  screen,
  state,
  onRun,
}: {
  screen: AxisCard[] | null;
  state: StageState;
  onRun?: () => void;
}) {
  if (state === "not_run" || !screen) {
    return (
      <StageNotYetRun
        stage="Run three-axis screen"
        description="Founder, Market, and Idea-vs-Market are scored independently. They are never averaged into a single number — each axis renders its own verdict, trend, and rationale."
        ctaLabel="Run screen"
        onRun={onRun}
      />
    );
  }
  return (
    <section>
      <SectionHead
        eyebrow="stage 02"
        title="Three-axis screen"
        subtitle="Three independent verdicts. No composite score."
      />
      <div className="mt-6 grid gap-5 md:grid-cols-3">
        {screen.map((axis) => (
          <AxisCardView key={axis.key} axis={axis} />
        ))}
      </div>
      <p className="mt-6 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/40">
        by design: these three verdicts are not summed, averaged, or ranked against each other.
      </p>
    </section>
  );
}

function AxisCardView({ axis }: { axis: AxisCard }) {
  const verdictColor: Record<AxisVerdict, string> = {
    pass: "var(--verified)",
    concern: "var(--contested-amber)",
    fail: "var(--contested-red)",
  };
  const color = verdictColor[axis.verdict];
  return (
    <article
      className="fancy-card gradient-border glow-card flex h-full flex-col rounded-2xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-5 text-[var(--ink)] shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]"
      style={{ borderTop: `3px solid ${color}` }}
    >
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          axis · {axis.label.toLowerCase()}
        </div>
        <TrendArrow trend={axis.trend} />
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span
          className="font-display text-2xl font-medium tracking-tight"
          style={{ color }}
        >
          {axis.verdict.toUpperCase()}
        </span>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--ink)]/90">
        {axis.headline}
      </p>
      <div className="mt-3">
        <AgentRationale agent="Screening Agent" surface="paper">
          {axis.rationale}
        </AgentRationale>
      </div>
      <ul className="mt-4 space-y-1.5 border-t border-[var(--ink)]/10 pt-3">
        {axis.factors.map((f) => (
          <li
            key={f}
            className="flex items-start gap-2 font-mono text-[11px] text-[var(--ink)]/70"
          >
            <span aria-hidden className="mt-1.5 h-1 w-1 rounded-full bg-[var(--ink)]/40" />
            {f}
          </li>
        ))}
      </ul>
    </article>
  );
}

// ─── Diligence tab ───────────────────────────────────────────────────────────
/** Deterministic per-claim note from the Diligence Judge — derived from
 *  trust + verdict + linked signals. Additive; keeps existing mock data intact. */
function diligenceJudgeNote(
  c: Claim,
  d: Application["diligence"],
): string {
  const supporting = (d?.signals ?? []).filter((s) =>
    (s.supports ?? []).includes(c.id),
  );
  const contradicting = (d?.signals ?? []).filter((s) =>
    (s.contradicts ?? []).includes(c.id),
  );
  const parts: string[] = [];
  if (c.trust === "high")
    parts.push(
      `Verdict: supported by ${supporting.length || "corroborating"} independent signal${supporting.length === 1 ? "" : "s"}.`,
    );
  else if (c.trust === "med")
    parts.push(
      "Verdict: partially supported — one corroborating signal, remaining evidence indirect.",
    );
  else if (c.trust === "low")
    parts.push(
      "Verdict: unverifiable — no public signal directly corroborates this claim.",
    );
  else if (c.trust === "contradicted")
    parts.push(
      `Verdict: contradicted — ${contradicting.length || "a"} signal directly opposes this claim.`,
    );
  else parts.push("Trust level not yet assigned.");

  if (!c.source_span)
    parts.push("No verbatim quote in the deck; inference flagged.");
  return parts.join(" ");
}

function DiligenceTab({
  claims,
  diligence,
  state,
}: {
  claims: Claim[];
  diligence: Application["diligence"];
  state: StageState;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [activeClaim, setActiveClaim] = useState<string | null>(null);

  // signalId -> claimIds it contradicts. Hook must run before any early return.
  const contradictionsBySignal = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const s of diligence?.signals ?? []) {
      if (s.contradicts?.length) m.set(s.id, s.contradicts);
    }
    return m;
  }, [diligence?.signals]);

  if (state === "not_run" || !diligence) {
    return (
      <StageNotYetRun
        stage="Run diligence"
        description="Diligence assigns a trust level and verdict to every claim by pulling corroborating (or contradicting) signals from public sources. Gaps are surfaced as visible annotations, never buried."
        ctaLabel="Run diligence"
      />
    );
  }

  return (
    <section>
      <SectionHead
        eyebrow="stage 03"
        title="Diligence"
        subtitle="Trust + verdict per claim. Contradictions thread to the signal that broke them."
      />

      <div ref={containerRef} className="relative mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Claims (with trust + verdict) */}
        <ul className="space-y-4">
          {claims.map((c) => {
            const isContradicted = c.trust === "contradicted";
            return (
              <li key={c.id}>
                <div
                  onMouseEnter={() => isContradicted && setActiveClaim(c.id)}
                  onMouseLeave={() =>
                    setActiveClaim((cur) => (cur === c.id ? null : cur))
                  }
                  onClick={() =>
                    isContradicted &&
                    setActiveClaim((cur) => (cur === c.id ? null : c.id))
                  }
                  className={isContradicted ? "cursor-pointer" : ""}
                >
                  <ClaimRow claim={c} showTrust idPrefix="dil-claim" />
                  <div className="mt-2">
                    <AgentRationale agent="Diligence Judge" surface="paper">
                      {diligenceJudgeNote(c, diligence)}
                    </AgentRationale>
                  </div>
                  {isContradicted && (
                    <div className="mt-2 font-mono text-[11px] text-[var(--contested-red)]/85">
                      hover / click to trace the contradicting signal →
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>

        {/* Signals + gaps rail */}
        <aside className="space-y-6">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
              diligence signals
            </div>
            <ul className="mt-3 space-y-3">
              {diligence.signals.map((s) => {
                const contradictedClaimId = contradictionsBySignal.get(s.id)?.[0];
                const active =
                  contradictedClaimId != null && activeClaim === contradictedClaimId;
                return (
                  <li key={s.id}>
                    <SignalCard signal={s} id={`dil-signal-${s.id}`} active={active} />
                  </li>
                );
              })}
            </ul>
          </div>

          <div>
            <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
              open gaps · annotated
            </div>
            <ul className="mt-3 space-y-2">
              {diligence.gaps.map((g) => (
                <GapNote key={g.id} gap={g} />
              ))}
            </ul>
          </div>
        </aside>

        {/* Evidence threads — active only for the hovered/selected contradicted claim */}
        {activeClaim &&
          diligence.signals
            .filter((s) => s.contradicts?.includes(activeClaim))
            .map((s) => (
              <EvidenceThread
                key={s.id}
                fromId={`dil-claim-${activeClaim}`}
                toId={`dil-signal-${s.id}`}
                trust={"contradicted" as TrustLevel}
                container={containerRef}
              />
            ))}
      </div>
    </section>
  );
}

function SignalCard({
  signal,
  id,
  active,
}: {
  signal: DiligenceSignal;
  id: string;
  active: boolean;
}) {
  const isContradicting = (signal.contradicts?.length ?? 0) > 0;
  const accent = isContradicting ? "var(--contested-red)" : "var(--verified)";
  return (
    <article
      id={id}
      className="fancy-card gradient-border glow-card rounded-2xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-3 shadow-[0_20px_50px_-44px_rgba(24,33,70,0.55)] transition-shadow"
      style={{
        borderColor: active
          ? accent
          : "color-mix(in oklab, var(--ink) 12%, transparent)",
        boxShadow: active ? `0 0 0 1px ${accent} inset` : "none",
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          {isContradicting ? "contradicts" : "supports"}
        </div>
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: accent }}
        />
      </div>
      <div className="mt-1.5 font-mono text-[11px] text-[var(--ink)]/60">
        {signal.source}
      </div>
      <blockquote className="mt-2 font-mono text-[12px] leading-relaxed text-[var(--ink)]/85">
        &ldquo;{signal.quote}&rdquo;
      </blockquote>
      <div className="mt-2 flex flex-wrap gap-1">
        {(signal.supports ?? []).map((cid) => (
          <span
            key={cid}
            className="rounded-sm border border-[var(--verified)]/40 px-1.5 py-0.5 font-mono text-[10px] text-[var(--verified)]"
          >
            → {cid}
          </span>
        ))}
        {(signal.contradicts ?? []).map((cid) => (
          <span
            key={cid}
            className="rounded-sm border border-[var(--contested-red)]/50 px-1.5 py-0.5 font-mono text-[10px] text-[var(--contested-red)]"
          >
            ✗ {cid}
          </span>
        ))}
      </div>
    </article>
  );
}

function GapNote({ gap }: { gap: DiligenceGap }) {
  return (
    <li
      className="relative rounded-sm px-3 py-2 font-mono text-[12px] leading-relaxed text-[var(--ink)]"
      style={{
        background: "color-mix(in oklab, var(--contested-amber) 55%, #F5EFD4)",
        boxShadow:
          "0 1px 0 0 rgba(0,0,0,0.04), inset 0 -6px 10px -8px rgba(0,0,0,0.15)",
        transform: "rotate(-0.2deg)",
      }}
    >
      <div className="text-[var(--ink)]">{gap.label}</div>
      {gap.note && (
        <div className="mt-1 text-[11px] text-[var(--ink)]/65">{gap.note}</div>
      )}
    </li>
  );
}

// ─── Memo tab ────────────────────────────────────────────────────────────────
function MemoTab({
  memo,
  claims,
  state,
  onJumpToClaim,
}: {
  memo: Memo | null;
  claims: Claim[];
  state: StageState;
  onJumpToClaim: () => void;
}) {
  if (state === "not_run" || !memo) {
    return (
      <StageNotYetRun
        stage="Draft memo"
        description="The memo threads back to specific claim IDs. Snapshot, hypotheses, SWOT, problem/product, and traction — plus a recommendation with based_on claim IDs you can click back to."
        ctaLabel="Draft memo"
      />
    );
  }
  const claimIndex = new Map(claims.map((c) => [c.id, c]));
  return (
    <section>
      <SectionHead
        eyebrow="stage 04"
        title="Investment memo"
        subtitle="Prose sections. Recommendation is threaded to the exact claims that support it."
      />
      {/* Caption attributing the memo prose to the Memo Agent */}
      <div className="mt-3 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/40">
        {(() => {
          const Icon = AGENT_ICON["Memo Agent"];
          return <Icon size={11} strokeWidth={1.75} aria-hidden />;
        })()}
        <span>generated by memo agent</span>
      </div>
      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <MemoSection label="Snapshot">{memo.snapshot}</MemoSection>
        <MemoSection label="Problem / product">{memo.problem_product}</MemoSection>
        <MemoSection label="Traction & KPIs">{memo.traction_kpis}</MemoSection>
        <MemoSection label="Hypotheses">
          <ul className="mt-1 space-y-2">
            {memo.hypotheses.map((h, i) => (
              <li key={i} className="flex gap-2 text-[15px] leading-relaxed">
                <span className="font-mono text-[11px] text-[var(--ink)]/45">
                  H{i + 1}
                </span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </MemoSection>
      </div>

      <div className="fancy-card mt-5 rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_28px_70px_-58px_rgba(24,33,70,0.7)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          swot
        </div>
        <div className="mt-3 grid gap-4 md:grid-cols-4">
          <SwotCell label="Strengths" items={memo.swot.strengths} accent="var(--verified)" />
          <SwotCell label="Weaknesses" items={memo.swot.weaknesses} accent="var(--contested-red)" />
          <SwotCell label="Opportunities" items={memo.swot.opportunities} accent="var(--signal)" />
          <SwotCell label="Threats" items={memo.swot.threats} accent="var(--contested-amber)" />
        </div>
      </div>

      {/* Recommendation */}
      <div
        className="fancy-card mt-5 rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_28px_70px_-58px_rgba(24,33,70,0.7)]"
        style={{ borderLeft: `3px solid var(--signal)` }}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
              recommendation
            </div>
            <div className="mt-1 flex items-baseline gap-3">
              <span
                className="font-display text-3xl font-medium tracking-tight uppercase"
                style={{
                  color:
                    memo.recommendation.verdict === "invest"
                      ? "var(--verified)"
                      : memo.recommendation.verdict === "pass"
                        ? "var(--contested-red)"
                        : "var(--contested-amber)",
                }}
              >
                {memo.recommendation.verdict}
              </span>
              {memo.recommendation.amount_usd != null && (
                <span className="font-mono text-lg text-[var(--ink)]/85">
                  ${memo.recommendation.amount_usd.toLocaleString()}
                </span>
              )}
            </div>
          </div>
        </div>
        <p className="mt-4 max-w-[70ch] text-[15px] leading-relaxed text-[var(--ink)]/85">
          {memo.recommendation.rationale}
        </p>
        <div className="mt-5 border-t border-[var(--ink)]/10 pt-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            based on
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {memo.recommendation.based_on.map((cid) => {
              const c = claimIndex.get(cid);
              return (
                <button
                  key={cid}
                  type="button"
                  onClick={() => {
                    onJumpToClaim();
                    // wait a tick for tab switch to render
                    requestAnimationFrame(() => {
                      const el = document.getElementById(`dil-claim-${cid}`);
                      el?.scrollIntoView({ behavior: "smooth", block: "center" });
                    });
                  }}
                  className="inline-flex items-center gap-1.5 rounded-sm border border-[var(--signal)]/40 px-2 py-1 font-mono text-[11px] text-[var(--signal)] transition-colors hover:bg-[color-mix(in_oklab,var(--signal)_10%,transparent)]"
                  title={c?.text ?? cid}
                >
                  <span aria-hidden className="h-1 w-1 rounded-full bg-[var(--signal)]" />
                  {cid}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function MemoSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="fancy-card gradient-border glow-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.65)]">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
        {label}
      </div>
      <div className="mt-2 text-[15px] leading-relaxed text-[var(--ink)]/90">
        {children}
      </div>
    </div>
  );
}

function SwotCell({
  label,
  items,
  accent,
}: {
  label: string;
  items: string[];
  accent: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
        <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          {label}
        </span>
      </div>
      <ul className="mt-2 space-y-1.5">
        {items.map((it, i) => (
          <li key={i} className="text-[13px] leading-relaxed text-[var(--ink)]/85">
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Adversary tab ───────────────────────────────────────────────────────────
function AdversaryTab({
  adversary,
  state,
  memoReady,
  running,
  onRun,
}: {
  adversary: Adversary | null;
  state: StageState;
  memoReady: boolean;
  running: boolean;
  onRun: () => void;
}) {
  if (state === "not_run" || !adversary) {
    if (!memoReady) {
      return (
        <StageNotYetRun
          stage="Draft the memo first"
          description="The adversarial pass runs against the drafted memo. Draft the memo, then run Devil's Advocate to generate persona objections, verify each one, and produce the decision brief."
          ctaLabel="Back to memo"
        />
      );
    }
    return (
      <div className="fancy-card rounded-3xl border border-dashed border-[var(--ink)]/20 bg-[var(--surface-card-soft)] p-8">
        <div className="flex items-start gap-5">
          <div
            aria-hidden
            className="mt-1 h-10 w-10 shrink-0 rounded-sm border border-[var(--ink)]/15"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, transparent 0 4px, color-mix(in oklab, var(--ink) 8%, transparent) 4px 5px)",
            }}
          />
          <div className="flex-1">
            <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
              stage · not yet run
            </div>
            <h3 className="mt-1 font-display text-xl font-medium tracking-tight text-[var(--ink)]">
              Run Devil's Advocate
            </h3>
            <p className="mt-2 max-w-[62ch] text-sm text-[var(--ink)]/65">
              Four adversarial personas cross-examine the memo. Each objection is
              labeled evidence-backed or speculation, and marked verified /
              unverified / n/a. The output ends with a decision brief the human
              uses at the gate.
            </p>
            <button
              type="button"
              onClick={onRun}
              disabled={running}
              className="mt-5 inline-flex items-center gap-2 rounded-sm px-4 py-2 text-sm font-medium text-[var(--paper)] transition-colors disabled:opacity-50"
              style={{ background: "var(--contested-red)" }}
            >
              {running ? (
                <AgentWorking agent="Adversary Agent" surface="ink" />
              ) : (
                <>
                  <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--paper)]" />
                  Run Devil's Advocate
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section>
      <SectionHead
        eyebrow="stage 05"
        title="Devil's advocate"
        subtitle="Persona objections + case-file decision brief. Threaded to claim IDs."
      />

      {/* Decision brief — case file at the top */}
      <div className="mt-6">
        <DecisionBriefCard brief={adversary.decision_brief} surface="paper" />
      </div>

      {/* Objections grid */}
      <div className="mt-6">
        <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
          objections · by persona
        </div>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          {adversary.objections.map((o) => (
            <ObjectionCard key={o.id} objection={o} />
          ))}
        </div>
      </div>

      {/* Bull / bear */}
      <div className="mt-8 grid gap-5 md:grid-cols-2">
        <div
          className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.65)]"
          style={{ borderTop: `3px solid var(--verified)` }}
        >
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            bull case
          </div>
          <p className="mt-2 text-[15px] leading-relaxed text-[var(--ink)]/90">
            {adversary.bull_case}
          </p>
        </div>
        <div
          className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.65)]"
          style={{ borderTop: `3px solid var(--contested-red)` }}
        >
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            bear case
          </div>
          <p className="mt-2 text-[15px] leading-relaxed text-[var(--ink)]/90">
            {adversary.bear_case}
          </p>
        </div>
      </div>

      {/* Kill criteria */}
      <div className="fancy-card mt-5 rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-6 text-[var(--ink)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.65)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          kill criteria
        </div>
        <ul className="mt-3 space-y-2">
          {adversary.kill_criteria.map((k, i) => (
            <li
              key={i}
              className="flex gap-3 border-l-2 border-[var(--contested-red)]/50 pl-3 text-[14px] leading-relaxed text-[var(--ink)]/85"
            >
              <span className="font-mono text-[11px] text-[var(--ink)]/45">
                K{i + 1}
              </span>
              <span>{k}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ─── Section header ──────────────────────────────────────────────────────────
function SectionHead({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div>
      <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
        {eyebrow}
      </div>
      <h2 className="mt-1 font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
        {title}
      </h2>
      {subtitle && <p className="mt-1 text-sm text-[var(--ink)]/60">{subtitle}</p>}
    </div>
  );
}
