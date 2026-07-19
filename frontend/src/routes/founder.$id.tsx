import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { OriginTag, TrendArrow, UncertaintyBand } from "@/components/ds";
import type { Founder } from "@/lib/dashboard-data";
import type {
  Application,
  FounderProfile,
  Signal,
} from "@/lib/founder-profiles";

export const Route = createFileRoute("/founder/$id")({
  component: FounderProfilePage,
});

type ApiResponse = { founder: Founder; profile: FounderProfile };
type ActivateResponse = {
  founder_id: string;
  outreach_draft: string;
  status: "draft";
  drafted_at: string;
};

function FounderProfilePage() {
  const { id } = Route.useParams();
  const [data, setData] = useState<ApiResponse | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [activating, setActivating] = useState(false);
  const [draft, setDraft] = useState<ActivateResponse | null>(null);

  useEffect(() => {
    setData(null);
    setNotFound(false);
    setDraft(null);
    fetch(`/api/founders/${id}`)
      .then(async (r) => {
        if (r.status === 404) {
          setNotFound(true);
          return null;
        }
        return r.json();
      })
      .then((d: ApiResponse | null) => d && setData(d));
  }, [id]);

  async function activate() {
    setActivating(true);
    try {
      const res = await fetch(`/api/founders/${id}/activate`, {
        method: "POST",
      });
      const body = (await res.json()) as ActivateResponse;
      setDraft(body);
    } finally {
      setActivating(false);
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-[1100px] px-6 py-12 md:px-10">
        <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-hero)] p-6 shadow-[0_40px_90px_-70px_rgba(27,37,94,0.8)] md:p-8">
          <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
            not found
          </div>
          <h1 className="mt-1 font-display text-2xl font-medium tracking-tight">
            No founder with id{" "}
            <span className="font-mono text-[var(--ink)]/80">{id}</span>
          </h1>
          <Link
            to="/founder"
            className="mt-4 inline-block font-mono text-[11px] uppercase tracking-widest text-[var(--signal)] underline underline-offset-4"
          >
            back to founder list
          </Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-[1100px] px-6 py-10 md:px-10 md:py-12">
        <div className="h-6 w-40 animate-pulse rounded bg-[var(--paper)]/10" />
        <div className="mt-3 h-9 w-96 animate-pulse rounded bg-[var(--paper)]/10" />
        <div className="mt-8 h-32 animate-pulse rounded-md bg-[var(--ink)]/[0.06]" />
      </div>
    );
  }

  const { founder, profile } = data;

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-10 md:px-10 md:py-12">
      {/* Back link */}
      <Link
        to="/founder"
        className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/50 hover:text-[var(--ink)]/90"
      >
        ← founder list
      </Link>

      {/* Header */}
      <header className="fancy-card relative mt-4 grid gap-6 overflow-hidden rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-hero)] p-6 shadow-[0_40px_90px_-70px_rgba(27,37,94,0.8)] md:grid-cols-[1fr_360px] md:p-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(520px_240px_at_10%_-10%,rgba(61,90,254,0.22),transparent_60%)]" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(520px_240px_at_90%_-10%,rgba(56,189,248,0.18),transparent_60%)]" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-4xl font-semibold tracking-tight text-[var(--ink)]">
              {founder.name}
            </h1>
            <OriginTag origin={founder.origin} />
            {founder.has_open_app && (
              <span className="rounded-full border border-[var(--signal)]/30 bg-[var(--surface-accent)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]">
                open app
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-[var(--ink)]/50">
            <span>{founder.handle}</span>
            <span>·</span>
            <span>{profile.location}</span>
            <span>·</span>
            <span>id · {founder.id}</span>
          </div>
          <p className="mt-4 max-w-[60ch] font-display text-lg tracking-tight text-[var(--ink)]/85">
            {profile.headline}
          </p>
          <p className="mt-3 max-w-[68ch] text-sm text-[var(--ink)]/65">
            {profile.bio}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={activate}
              disabled={activating}
              className="rounded-full border border-[var(--signal)]/30 bg-[var(--signal)] px-5 py-2.5 text-sm font-semibold text-[var(--paper)] shadow-[0_12px_28px_-18px_rgba(61,90,254,0.7)] transition-colors hover:bg-[color-mix(in_oklab,var(--signal)_88%,white)] disabled:opacity-50"
            >
              {activating
                ? "Drafting…"
                : draft
                  ? "Regenerate draft"
                  : "Activate"}
            </button>
            <span className="font-mono text-[11px] text-[var(--ink)]/45">
              drafts outreach — never sends
            </span>
          </div>
        </div>

        {/* Score block */}
        <ScoreBlock founder={founder} profile={profile} />
      </header>

      <section className="mt-6 grid gap-3 rounded-3xl border border-[var(--glass-border)] bg-[var(--glass)] p-4 shadow-[0_24px_60px_-50px_rgba(27,37,94,0.7)] backdrop-blur md:grid-cols-4">
        <KpiStat label="founder score" value={String(founder.score)} />
        <KpiStat label="band" value={`± ${founder.band}`} />
        <KpiStat label="signals" value={String(profile.signals.length)} />
        <KpiStat label="applications" value={String(profile.applications.length)} />
      </section>

      {/* Outreach draft panel */}
      {draft && <OutreachPanel draft={draft} onDismiss={() => setDraft(null)} />}

      {/* Body: signals + applications */}
      <div className="mt-10 grid gap-10 md:grid-cols-[1fr_320px]">
        <EvidenceTimeline signals={profile.signals} />
        <Applications
          apps={profile.applications}
          founderName={founder.name}
        />
      </div>
    </div>
  );
}

function KpiStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
        {label}
      </div>
      <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
        {value}
      </div>
    </div>
  );
}

function ScoreBlock({
  founder,
  profile,
}: {
  founder: Founder;
  profile: FounderProfile;
}) {
  return (
    <div className="fancy-card gradient-border glow-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-5 shadow-[0_30px_70px_-58px_rgba(24,33,70,0.7)]">
      <div className="flex items-start justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
          founder score
        </div>
        <TrendArrow trend={founder.trend} />
      </div>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="font-mono text-6xl font-medium leading-none tabular-nums text-[var(--ink)]">
          {founder.score}
        </span>
        <span className="font-mono text-sm text-[var(--ink)]/55">
          ± {founder.band}
        </span>
      </div>
      <div className="mt-3">
        <UncertaintyBand score={founder.score} band={founder.band} />
      </div>
      <div className="mt-5 border-t border-[var(--ink)]/10 pt-4">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
          score history
        </div>
        <Sparkline data={profile.score_history} />
      </div>
    </div>
  );
}

function Sparkline({
  data,
}: {
  data: Array<{ at: string; score: number }>;
}) {
  const { path, area, points, min, max, first, last } = useMemo(() => {
    const w = 300;
    const h = 68;
    const pad = 4;
    const scores = data.map((d) => d.score);
    const min = Math.min(...scores);
    const max = Math.max(...scores);
    const span = Math.max(1, max - min);
    const stepX = data.length > 1 ? (w - pad * 2) / (data.length - 1) : 0;
    const pts = data.map((d, i) => {
      const x = pad + i * stepX;
      const y = h - pad - ((d.score - min) / span) * (h - pad * 2);
      return { x, y };
    });
    const path = pts
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
      .join(" ");
    const area =
      path +
      ` L ${pts[pts.length - 1]!.x.toFixed(1)} ${h - pad} L ${pts[0]!.x.toFixed(1)} ${h - pad} Z`;
    return {
      path,
      area,
      points: pts,
      min,
      max,
      first: data[0]!,
      last: data[data.length - 1]!,
    };
  }, [data]);

  return (
    <div className="mt-2">
      <svg
        viewBox="0 0 300 68"
        className="h-[68px] w-full"
        preserveAspectRatio="none"
        aria-label="Score history"
      >
        <path d={area} fill="var(--signal)" opacity="0.10" />
        <path
          d={path}
          fill="none"
          stroke="var(--signal)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {points.length > 0 && (
          <circle
            cx={points[points.length - 1]!.x}
            cy={points[points.length - 1]!.y}
            r="2.5"
            fill="var(--signal)"
          />
        )}
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--ink)]/45">
        <span>
          {new Date(first.at).toISOString().slice(0, 10)} · {first.score}
        </span>
        <span>
          range {min}–{max}
        </span>
        <span>
          {new Date(last.at).toISOString().slice(0, 10)} · {last.score}
        </span>
      </div>
    </div>
  );
}

function EvidenceTimeline({ signals }: { signals: Signal[] }) {
  return (
    <section>
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
          memory
        </span>
        <h2 className="font-display text-lg font-medium tracking-tight text-[var(--ink)]/90">
          Evidence timeline
        </h2>
        <span className="text-xs text-[var(--ink)]/45">
          raw signals — not claims yet
        </span>
      </div>

      {signals.length === 0 ? (
        <p className="mt-5 text-sm text-[var(--ink)]/55">
          No signals in memory yet.
        </p>
      ) : (
        <div className="mt-5 overflow-hidden rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.65)]">
          <div className="grid grid-cols-[120px_120px_1fr_120px] gap-3 border-b border-[var(--ink)]/10 bg-[var(--glass)] px-4 py-3 text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
            <span>origin</span>
            <span>kind</span>
            <span>signal</span>
            <span className="text-right">time</span>
          </div>
          <ol className="divide-y divide-[var(--ink)]/10">
            {signals.map((s) => (
              <li key={s.id} className="group">
                <SignalRow s={s} />
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function SignalRow({ s }: { s: Signal }) {
  const when = new Date(s.at);
  const rel = relativeTime(when);
  return (
    <div className="grid grid-cols-[120px_120px_1fr_120px] gap-3 px-4 py-4 text-[12px] text-[var(--ink)]/80">
      <div>
        <OriginTag origin={s.source} />
      </div>
      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
        {s.kind}
      </div>
      <div className="min-w-0">
        <p className="truncate text-[13px] text-[var(--ink)]/85">{s.text}</p>
      </div>
      <div className="text-right font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
        {rel}
      </div>
    </div>
  );
}

function relativeTime(d: Date): string {
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const STATUS_STYLES: Record<Application["status"], string> = {
  screening: "border-[var(--contested-amber)]/50 text-[var(--contested-amber)]",
  diligence: "border-[var(--signal)]/50 text-[var(--signal)]",
  memo: "border-[var(--signal)]/50 text-[var(--signal)]",
  decision: "border-[var(--verified)]/50 text-[var(--verified)]",
  declined: "border-[var(--dim)]/50 text-[var(--dim)]",
};

function Applications({
  apps,
  founderName,
}: {
  apps: Application[];
  founderName: string;
}) {
  return (
    <aside>
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
          applications
        </span>
      </div>
      {apps.length === 0 ? (
        <div className="fancy-card mt-5 rounded-2xl border border-dashed border-[var(--ink)]/12 bg-[var(--surface-card-soft)] p-4 text-sm text-[var(--ink)]/60">
          No applications from {founderName} yet. Activation drafts an outreach
          instead.
        </div>
      ) : (
        <div className="mt-4 overflow-hidden rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.65)]">
          <div className="grid grid-cols-[1fr_110px_90px] gap-3 border-b border-[var(--ink)]/10 bg-[var(--glass)] px-4 py-3 text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
            <span>company</span>
            <span>status</span>
            <span className="text-right">submitted</span>
          </div>
          <ul className="divide-y divide-[var(--ink)]/10">
            {apps.map((a) => (
              <li key={a.id}>
                <Link
                  to="/application/$id"
                  params={{ id: a.id }}
                  className="flex items-center justify-between gap-3 px-4 py-4 text-[12px] text-[var(--ink)]/80"
                >
                  <div className="min-w-0">
                    <div className="truncate font-display text-[13px] font-semibold text-[var(--ink)]">
                      {a.company}
                    </div>
                    <div className="font-mono text-[10px] text-[var(--ink)]/50">
                      app {a.id}
                    </div>
                  </div>
                  <span
                    className={
                      "rounded-full border bg-transparent px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest " +
                      STATUS_STYLES[a.status]
                    }
                  >
                    {a.status}
                  </span>
                  <span className="text-right font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                    {new Date(a.submitted_at).toISOString().slice(0, 10)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

function OutreachPanel({
  draft,
  onDismiss,
}: {
  draft: ActivateResponse;
  onDismiss: () => void;
}) {
  return (
    <section className="fancy-card mt-8 rounded-3xl border border-[var(--signal)]/35 bg-[var(--surface-accent)] p-5 shadow-[0_28px_70px_-60px_rgba(61,90,254,0.6)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-sm bg-[var(--contested-amber)]/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--contested-amber)]">
            draft — not sent
          </span>
          <span className="font-mono text-[11px] text-[var(--ink)]/60">
            drafted {new Date(draft.drafted_at).toISOString().slice(0, 16)}Z
          </span>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/50 hover:text-[var(--ink)]"
        >
          dismiss
        </button>
      </div>
      <div className="mt-4 rounded-2xl bg-[var(--ink)] p-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]">
        <pre className="whitespace-pre-wrap font-body text-[14px] leading-relaxed text-[var(--paper)]/90">
          {draft.outreach_draft}
        </pre>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={() =>
            navigator.clipboard?.writeText(draft.outreach_draft).catch(() => {})
          }
          className="rounded-sm border border-[var(--ink)]/20 px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/85 hover:border-[var(--ink)]/40 hover:text-[var(--ink)]"
        >
          copy to clipboard
        </button>
        <span className="font-mono text-[11px] text-[var(--ink)]/45">
          human sends manually · no auto-send in this app
        </span>
      </div>
    </section>
  );
}
