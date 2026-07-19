import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  OriginTag,
  TrendArrow,
  UncertaintyBand,
  AGENT_ICON,
  type OriginKind,
  type TrendKind,
} from "@/components/ds";
import { AskFirstCheckConsole } from "@/components/ask-firstcheck";
import { useIsMobile } from "@/hooks/use-mobile";

type Founder = {
  id: string;
  name: string;
  handle: string;
  origin: OriginKind;
  score: number;
  band: number;
  trend: TrendKind;
  top_signals: string[];
  has_open_app: boolean;
};

type QueryResult = { founder: Founder; why_matched: string[] };
type ParsedQuery = {
  technical_founder: boolean | null;
  sectors: string[] | null;
  geos: string[] | null;
  shipped_within_days: number | null;
  prior_vc: boolean | null;
};

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

const ORIGIN_FILTERS: Array<OriginKind | "all"> = [
  "all",
  "github",
  "hn",
  "inbound",
  "synthetic",
];

function DashboardPage() {
  const [founders, setFounders] = useState<Founder[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [queryInput, setQueryInput] = useState("");
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const [matches, setMatches] = useState<Map<string, string[]> | null>(null);
  const [querying, setQuerying] = useState(false);
  const [parsed, setParsed] = useState<ParsedQuery | null>(null);

  const [originFilter, setOriginFilter] = useState<OriginKind | "all">("all");
  const [sortDesc, setSortDesc] = useState(true);
  const [compact, setCompact] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const isMobile = useIsMobile();

  useEffect(() => {
    let cancel = false;
    fetch("/api/dashboard")
      .then((r) => r.json())
      .then((data) => {
        if (cancel) return;
        setFounders(data.founders ?? []);
        setLoading(false);
      })
      .catch((e) => {
        if (cancel) return;
        setError(String(e));
        setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, []);

  async function runQuery(e?: React.FormEvent) {
    e?.preventDefault();
    const q = queryInput.trim();
    if (!q) return;
    setQuerying(true);
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q }),
      });
      const data = (await res.json()) as {
        q: string;
        parsed: ParsedQuery;
        results: QueryResult[];
      };
      const map = new Map<string, string[]>();
      data.results.forEach((r) => map.set(r.founder.id, r.why_matched));
      setMatches(map);
      setParsed(data.parsed);
      setActiveQuery(q);
    } finally {
      setQuerying(false);
    }
  }

  function clearQuery() {
    setActiveQuery(null);
    setMatches(null);
    setParsed(null);
    setQueryInput("");
  }

  const visible = useMemo(() => {
    if (!founders) return [];
    let list = founders;
    if (activeQuery && matches) {
      list = list.filter((f) => matches.has(f.id));
    }
    if (originFilter !== "all") {
      list = list.filter((f) => f.origin === originFilter);
    }
    list = [...list].sort((a, b) =>
      sortDesc ? b.score - a.score : a.score - b.score,
    );
    return list;
  }, [founders, activeQuery, matches, originFilter, sortDesc]);

  const stats = useMemo(() => {
    if (!founders || founders.length === 0) return null;
    const total = founders.length;
    const openApps = founders.filter((f) => f.has_open_app).length;
    const synthetic = founders.filter((f) => f.origin === "synthetic").length;
    const avgScore = Math.round(
      founders.reduce((sum, f) => sum + f.score, 0) / total,
    );
    return { total, openApps, synthetic, avgScore };
  }, [founders]);

  const scoreBuckets = useMemo(() => {
    if (!founders || founders.length === 0) return [] as number[];
    const buckets = Array.from({ length: 5 }, () => 0);
    founders.forEach((f) => {
      const idx = Math.min(4, Math.floor(f.score / 20));
      buckets[idx] += 1;
    });
    return buckets;
  }, [founders]);

  return (
    <div
      className={
        "mx-auto max-w-[1200px] px-6 py-10 md:px-10 md:py-12 " +
        (askOpen && !isMobile ? "pr-[440px]" : "")
      }
    >
      <div className="grid gap-8">
        {/* Header */}
        <header className="fancy-card relative grid gap-4 overflow-hidden rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-hero)] p-6 shadow-[0_40px_90px_-70px_rgba(27,37,94,0.8)] md:grid-cols-[1.2fr_0.8fr] md:p-8">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(600px_280px_at_20%_-10%,rgba(61,90,254,0.22),transparent_60%)]" />
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(520px_240px_at_90%_-10%,rgba(56,189,248,0.18),transparent_60%)]" />
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent)] px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/70">
              dashboard · evidence ledger
            </div>
            <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight text-[var(--ink)] md:text-4xl">
              Founders, signals, and the proof trail
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink)]/60">
              Ranked by Founder Score with visible uncertainty. Every row traces
              back to its origin — no averaged composites, no hidden weights.
            </p>
          </div>
          <div className="relative flex flex-col justify-between gap-4 rounded-2xl border border-[var(--glass-border)] bg-[var(--glass)] p-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.45)] backdrop-blur">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
              snapshot
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3 shadow-[0_18px_40px_-32px_rgba(24,33,70,0.5)] transition-transform duration-200 hover:-translate-y-0.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                  founders
                </div>
                <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
                  {founders ? founders.length : "—"}
                </div>
              </div>
              <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3 shadow-[0_18px_40px_-32px_rgba(24,33,70,0.5)] transition-transform duration-200 hover:-translate-y-0.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                  open apps
                </div>
                <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
                  {stats ? stats.openApps : "—"}
                </div>
              </div>
              <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3 shadow-[0_18px_40px_-32px_rgba(24,33,70,0.5)] transition-transform duration-200 hover:-translate-y-0.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                  synthetic
                </div>
                <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
                  {stats ? stats.synthetic : "—"}
                </div>
              </div>
              <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3 shadow-[0_18px_40px_-32px_rgba(24,33,70,0.5)] transition-transform duration-200 hover:-translate-y-0.5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                  avg score
                </div>
                <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
                  {stats ? stats.avgScore : "—"}
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3 shadow-[0_18px_40px_-32px_rgba(24,33,70,0.5)]">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                  score distribution
                </span>
                <span className="font-mono text-[10px] text-[var(--ink)]/40">
                  0–100
                </span>
              </div>
              <ScoreHistogram data={scoreBuckets} />
            </div>
          </div>
        </header>

      {/* Query bar */}
      <section>
        <form onSubmit={runQuery} className="relative">
          <div className="fancy-card flex items-stretch overflow-hidden rounded-2xl border border-[var(--glass-border)] bg-[var(--glass)] shadow-[0_24px_60px_-50px_rgba(27,37,94,0.7)] backdrop-blur focus-within:border-[var(--signal)]">
            <div className="flex items-center pl-4 pr-3 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/55">
              query
            </div>
            <input
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="technical founder, AI infra, shipped last 30 days, no prior VC"
              className="flex-1 bg-transparent py-4 pr-4 text-[15px] text-[var(--ink)] placeholder:text-[var(--ink)]/35 focus:outline-none"
            />
            <button
              type="submit"
              disabled={querying || !queryInput.trim()}
              className="border-l border-[var(--glass-border)] bg-[var(--signal)] px-6 text-sm font-semibold text-[var(--paper)] shadow-[0_10px_24px_-16px_rgba(61,90,254,0.8)] transition-colors hover:bg-[color-mix(in_oklab,var(--signal)_88%,white)] disabled:opacity-40"
            >
              {querying ? "…" : "run"}
            </button>
          </div>
        </form>

        {activeQuery && (
          <div className="mt-3 flex items-center gap-3 text-xs">
            <span className="font-mono text-[11px] text-[var(--ink)]/50">
              filtered by
            </span>
            <span className="font-mono text-[11px] text-[var(--signal)]">
              “{activeQuery}”
            </span>
            <span className="text-[var(--ink)]/40">·</span>
            <button
              type="button"
              onClick={clearQuery}
              className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/60 underline decoration-[var(--ink)]/20 underline-offset-4 hover:text-[var(--ink)]"
            >
              clear filter, show all
            </button>
          </div>
        )}
      </section>

      {/* Sort / filter row */}
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
            origin
          </span>
          <div className="flex flex-wrap gap-1.5">
            {ORIGIN_FILTERS.map((o) => (
              <button
                key={o}
                type="button"
                onClick={() => setOriginFilter(o)}
                className={
                  "rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-widest transition-colors " +
                  (originFilter === o
                    ? "border-[var(--signal)]/30 bg-[var(--surface-accent)] text-[var(--signal)]"
                    : "border-[var(--ink)]/10 text-[var(--ink)]/60 hover:border-[var(--ink)]/20 hover:text-[var(--ink)]")
                }
              >
                {o}
              </button>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setSortDesc((v) => !v)}
          className="rounded-full border border-[var(--ink)]/10 bg-white/70 px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/70 shadow-[0_10px_24px_-20px_rgba(27,37,94,0.45)] hover:text-[var(--ink)]"
        >
          sort · score {sortDesc ? "high → low" : "low → high"}
        </button>
        <button
          type="button"
          onClick={() => setCompact((v) => !v)}
          className="rounded-full border border-[var(--ink)]/10 bg-white/70 px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/70 shadow-[0_10px_24px_-20px_rgba(27,37,94,0.45)] hover:text-[var(--ink)]"
        >
          {compact ? "Comfortable view" : "Compact view"}
        </button>
      </section>

      {/* Query Agent parsed view */}
      {activeQuery && parsed && <QueryAgentReadout parsed={parsed} />}

      {/* Results */}
      <section className="pb-16">
        {loading && <SkeletonList />}
        {error && (
          <div className="rounded-md border border-[var(--contested-red)]/40 bg-[var(--contested-red)]/10 p-5 text-sm text-[var(--ink)]">
            Failed to load dashboard — {error}
          </div>
        )}
        {!loading && !error && visible.length === 0 && (
          <EmptyState
            hasFounders={(founders?.length ?? 0) > 0}
            queried={!!activeQuery}
            onClear={clearQuery}
          />
        )}
        <TableHeader />
        <div className={compact ? "space-y-3 density-compact" : "space-y-3"}>
          {visible.map((f) => (
            <FounderRow
              key={f.id}
              f={f}
              whyMatched={matches?.get(f.id) ?? []}
            />
          ))}
        </div>
      </section>
      </div>
      <button
        type="button"
        onClick={() => setAskOpen((v) => !v)}
        title="Ask FirstCheck"
        className="fixed bottom-6 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full border border-[var(--signal)]/35 bg-[var(--signal)] text-[var(--paper)] shadow-[0_18px_40px_-18px_rgba(61,90,254,0.75)] transition-transform hover:-translate-y-0.5"
        aria-label="Ask FirstCheck"
      >
        {(() => {
          const Icon = AGENT_ICON["Extractor Agent"];
          return <Icon size={18} strokeWidth={2} aria-hidden />;
        })()}
      </button>
      <AskFirstCheckConsole
        open={askOpen}
        onOpenChange={setAskOpen}
        founders={founders}
      />
    </div>
  );
}

function ScoreHistogram({ data }: { data: number[] }) {
  const max = Math.max(1, ...data);
  return (
    <div className="mt-2">
      <svg viewBox="0 0 120 36" className="h-9 w-full" aria-label="Score distribution">
        {data.map((v, i) => {
          const h = (v / max) * 28;
          const x = i * 24 + 6;
          const y = 32 - h;
          return (
            <rect
              key={i}
              x={x}
              y={y}
              width={12}
              height={h}
              rx={5}
              fill="var(--signal)"
              opacity={0.7}
            />
          );
        })}
        <path
          d="M2 32 H118"
          stroke="rgba(31,36,48,0.12)"
          strokeWidth="1"
        />
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--ink)]/40">
        <span>0–19</span>
        <span>80–100</span>
      </div>
    </div>
  );
}

function TableHeader() {
  return (
    <div className="grid grid-cols-[1fr_220px] gap-5 px-5 text-[10px] uppercase tracking-widest text-[var(--ink)]/45 md:px-6">
      <div className="flex items-center gap-3">
        <span>Founder</span>
        <span className="text-[var(--ink)]/30">·</span>
        <span>Signals</span>
      </div>
      <div className="text-right">Score</div>
    </div>
  );
}

function FounderRow({
  f,
  whyMatched,
}: {
  f: Founder;
  whyMatched: string[];
}) {
  const synthetic = f.origin === "synthetic";
  return (
      <Link
      to="/founder/$id"
      params={{ id: f.id }}
      className={
        "fancy-card group relative grid grid-cols-[1fr_auto] gap-5 overflow-hidden rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-5 text-[var(--ink)] shadow-[0_28px_70px_-60px_rgba(24,33,70,0.7)] transition-transform hover:-translate-y-[3px] md:grid-cols-[minmax(0,1fr)_220px] md:p-6 " +
        (synthetic ? "border-dashed border-[var(--dim)]/60" : "")
      }
    >
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
        <div className="absolute inset-0 bg-[radial-gradient(280px_140px_at_10%_0%,rgba(61,90,254,0.18),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(260px_140px_at_90%_0%,rgba(56,189,248,0.16),transparent_60%)]" />
      </div>
      {/* Left: identity + signals */}
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <h3 className="font-display text-xl font-semibold tracking-tight">
            {f.name}
          </h3>
          <span className="font-mono text-[11px] text-[var(--ink)]/50">
            {f.handle}
          </span>
          <OriginTag origin={f.origin} />
          {f.has_open_app && (
            <span
              className="inline-flex items-center gap-1.5 rounded-sm border border-[var(--signal)]/40 bg-[var(--signal)]/8 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]"
              title="Has open application"
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full bg-[var(--signal)]"
              />
              open app
            </span>
          )}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span className="rounded-full bg-[var(--accent)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/60">
            top signals
          </span>
        </div>
        <ul className="mt-2 space-y-1 text-[13px] text-[var(--ink)]/70">
          {f.top_signals.slice(0, 3).map((s, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-[7px] h-[3px] w-[3px] flex-shrink-0 rounded-full bg-[var(--ink)]/35" />
              <span className="truncate">{s}</span>
            </li>
          ))}
        </ul>

        {whyMatched.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {whyMatched.map((w, i) => (
              <span
                key={i}
                className="rounded-sm border border-[var(--signal)]/50 bg-[var(--signal)]/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]"
              >
                {w}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Right: score + trend — the "read from across the room" block */}
      <div className="relative rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-4 shadow-[0_18px_44px_-34px_rgba(27,37,94,0.6)] backdrop-blur transition-transform duration-200 group-hover:-translate-y-0.5">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
          founder score
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-4xl font-medium tabular-nums leading-none text-[var(--ink)]">
            {f.score}
          </span>
          <TrendArrow trend={f.trend} />
        </div>
        <div className="mt-3">
          <UncertaintyBand score={f.score} band={f.band} />
        </div>
      </div>
    </Link>
  );
}

function EmptyState({
  hasFounders,
  queried,
  onClear,
}: {
  hasFounders: boolean;
  queried: boolean;
  onClear: () => void;
}) {
  if (queried) {
    return (
      <div className="rounded-md border border-dashed border-[var(--ink)]/15 bg-[var(--paper)] p-8 text-center">
        <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
          no matches
        </div>
        <p className="mt-2 text-sm text-[var(--ink)]/70">
          No founder in the ledger matches this query. Try broader terms, or
          clear the filter.
        </p>
        <button
          type="button"
          onClick={onClear}
          className="mt-4 rounded-sm border border-[var(--ink)]/20 px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/80 hover:border-[var(--ink)]/40 hover:text-[var(--ink)]"
        >
          clear filter, show all
        </button>
      </div>
    );
  }
  if (!hasFounders) {
    return (
      <div className="rounded-md border border-dashed border-[var(--ink)]/15 bg-[var(--paper)] p-8">
        <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
          cache not loaded
        </div>
        <h3 className="mt-2 font-display text-lg text-[var(--ink)]">
          Founders will appear here once the scan cache loads.
        </h3>
        <p className="mt-2 max-w-xl text-sm text-[var(--ink)]/60">
          The scan pulls from GitHub, HN, and inbound decks on a schedule.
          Nothing is fabricated in this view — if it isn&rsquo;t here yet, it
          hasn&rsquo;t been seen yet. Synthetic rows are always dashed.
        </p>
      </div>
    );
  }
  return null;
}

function SkeletonList() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="grid grid-cols-[1fr_220px] gap-6 rounded-md border border-[var(--ink)]/8 bg-[var(--paper)] p-6"
        >
          <div className="space-y-3">
            <div className="h-5 w-1/3 rounded bg-[var(--ink)]/8" />
            <div className="h-3 w-2/3 rounded bg-[var(--ink)]/6" />
            <div className="h-3 w-1/2 rounded bg-[var(--ink)]/6" />
          </div>
          <div className="space-y-2">
            <div className="h-8 w-16 self-end rounded bg-[var(--ink)]/8" />
            <div className="h-2 w-full rounded bg-[var(--ink)]/6" />
          </div>
        </div>
      ))}
    </div>
  );
}

function QueryAgentReadout({ parsed }: { parsed: ParsedQuery }) {
  const Icon = AGENT_ICON["Query Agent"];
  const chips: Array<{ k: string; v: string }> = [];
  if (parsed.technical_founder !== null)
    chips.push({
      k: "technical_founder",
      v: parsed.technical_founder ? "true" : "false",
    });
  if (parsed.sectors?.length)
    chips.push({ k: "sectors", v: parsed.sectors.join(" · ") });
  if (parsed.geos?.length)
    chips.push({ k: "geos", v: parsed.geos.join(" · ") });
  if (parsed.shipped_within_days !== null)
    chips.push({ k: "shipped_within_days", v: String(parsed.shipped_within_days) });
  if (parsed.prior_vc !== null)
    chips.push({ k: "prior_vc", v: parsed.prior_vc ? "true" : "false" });

  return (
    <div className="mt-4 rounded-2xl border border-dashed border-[var(--ink)]/15 bg-[var(--paper)] px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          <Icon size={11} strokeWidth={1.75} aria-hidden />
          query agent read this as:
        </span>
        {chips.length === 0 ? (
          <span className="font-mono text-[11px] text-[var(--ink)]/45">
            no structured fields resolved · falling back to fuzzy match
          </span>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={c.k}
                className="rounded-sm border border-[var(--signal)]/50 bg-[var(--signal)]/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]"
              >
                {c.k} = {c.v}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
