import { useEffect, useRef, useState } from "react";
import {
  AGENT_ICON,
  EvidenceThread,
  OriginTag,
  TrendArrow,
  UncertaintyBand,
} from "@/components/ds";
import type { Founder } from "@/lib/dashboard-data";
import type { FounderProfile } from "@/lib/founder-profiles";

type ParsedQuery = {
  technical_founder: boolean | null;
  sectors: string[] | null;
  geos: string[] | null;
  shipped_within_days: number | null;
  prior_vc: boolean | null;
};

type QueryResult = { founder: Founder; why_matched: string[] };

type ChatMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "agent";
      query: string;
      parsed: ParsedQuery;
      results: QueryResult[];
      refinement?: {
        previous: ParsedQuery | null;
        changedKeys: string[];
      };
    };

type SummaryState = {
  founder: Founder;
  profile: FounderProfile;
};

type AskFirstCheckConsoleProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  founders: Founder[] | null;
};

const PLACEHOLDERS = [
  "AI infra founders in Berlin",
  "who improved their score this month",
  "cold-start founders worth a second look",
];

const EXAMPLE_QUERIES = [
  "AI infra founders in Berlin",
  "who is trending up",
  "cold-start founders worth a second look",
  "open source founders with no prior VC",
];

const SECTOR_TERMS: Array<[string, string]> = [
  ["ai infra", "AI infra"],
  ["ai", "AI"],
  ["saas", "SaaS"],
  ["deep tech", "deep tech"],
  ["fintech", "fintech"],
  ["biotech", "biotech"],
  ["dev tools", "dev tools"],
  ["open source", "open source"],
  ["llm", "LLM"],
  ["infra", "infra"],
];

const GEO_TERMS: Array<[string, string]> = [
  ["sf", "SF"],
  ["san francisco", "SF"],
  ["nyc", "NYC"],
  ["new york", "NYC"],
  ["london", "London"],
  ["berlin", "Berlin"],
  ["remote", "remote"],
  ["us", "US"],
  ["eu", "EU"],
];

const REFINE_PREFIX = [
  "now",
  "only",
  "just",
  "also",
  "instead",
  "then",
  "and",
  "filter",
  "refine",
  "add",
  "remove",
];

function isRefinement(text: string) {
  const lower = text.trim().toLowerCase();
  return REFINE_PREFIX.some((w) => lower.startsWith(`${w} `));
}

function stripRefinePrefix(text: string) {
  const tokens = text.trim().split(/\s+/);
  let i = 0;
  while (i < tokens.length) {
    const token = tokens[i]?.toLowerCase() ?? "";
    if (!REFINE_PREFIX.includes(token)) break;
    i += 1;
  }
  return tokens.slice(i).join(" ").trim();
}

function parseQueryClient(q: string): ParsedQuery {
  const s = q.toLowerCase();
  const technical_founder =
    /\btechnical\b/.test(s) || /\bengineer/.test(s) ? true : null;

  const sectors = SECTOR_TERMS.filter(([k]) => s.includes(k)).map(([, v]) => v);
  const geos = GEO_TERMS.filter(([k]) => s.includes(k)).map(([, v]) => v);

  let shipped_within_days: number | null = null;
  const m =
    s.match(/shipped[^0-9]*(\d+)\s*d/) ||
    s.match(/last\s*(\d+)\s*(?:d|day)/) ||
    s.match(/(\d+)\s*days?/);
  if (m) shipped_within_days = parseInt(m[1], 10);
  else if (/\blast month\b/.test(s)) shipped_within_days = 30;
  else if (/\blast week\b/.test(s)) shipped_within_days = 7;

  let prior_vc: boolean | null = null;
  if (/no prior vc|no vc|no funding|unfunded|bootstrap/.test(s)) prior_vc = false;
  else if (/prior vc|funded|raised/.test(s)) prior_vc = true;

  return {
    technical_founder,
    sectors: sectors.length ? Array.from(new Set(sectors)) : null,
    geos: geos.length ? Array.from(new Set(geos)) : null,
    shipped_within_days,
    prior_vc,
  };
}

function mergeParsed(prev: ParsedQuery, next: ParsedQuery): ParsedQuery {
  return {
    technical_founder:
      next.technical_founder !== null
        ? next.technical_founder
        : prev.technical_founder,
    sectors: next.sectors?.length ? next.sectors : prev.sectors,
    geos: next.geos?.length ? next.geos : prev.geos,
    shipped_within_days:
      next.shipped_within_days !== null
        ? next.shipped_within_days
        : prev.shipped_within_days,
    prior_vc: next.prior_vc !== null ? next.prior_vc : prev.prior_vc,
  };
}

function parsedToQuery(parsed: ParsedQuery) {
  const terms: string[] = [];
  if (parsed.technical_founder) terms.push("technical");
  if (parsed.sectors?.length)
    terms.push(...parsed.sectors.map((s) => s.toLowerCase()));
  if (parsed.geos?.length) terms.push(...parsed.geos.map((g) => g.toLowerCase()));
  if (parsed.shipped_within_days !== null)
    terms.push(`shipped last ${parsed.shipped_within_days} days`);
  if (parsed.prior_vc !== null)
    terms.push(parsed.prior_vc ? "prior vc" : "no prior vc");
  return terms.join(", ");
}

function parsedToChips(parsed: ParsedQuery) {
  const chips: Array<{ k: string; v: string }> = [];
  if (parsed.technical_founder !== null)
    chips.push({
      k: "technical_founder",
      v: parsed.technical_founder ? "true" : "false",
    });
  if (parsed.sectors?.length)
    chips.push({ k: "sectors", v: parsed.sectors.join(" / ") });
  if (parsed.geos?.length) chips.push({ k: "geos", v: parsed.geos.join(" / ") });
  if (parsed.shipped_within_days !== null)
    chips.push({ k: "shipped_within_days", v: String(parsed.shipped_within_days) });
  if (parsed.prior_vc !== null)
    chips.push({ k: "prior_vc", v: parsed.prior_vc ? "true" : "false" });
  return chips;
}

function diffParsed(prev: ParsedQuery | null, next: ParsedQuery) {
  if (!prev) return [] as string[];
  const changed: string[] = [];
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  if (!same(prev.technical_founder, next.technical_founder))
    changed.push("technical_founder");
  if (!same(prev.sectors, next.sectors)) changed.push("sectors");
  if (!same(prev.geos, next.geos)) changed.push("geos");
  if (!same(prev.shipped_within_days, next.shipped_within_days))
    changed.push("shipped_within_days");
  if (!same(prev.prior_vc, next.prior_vc)) changed.push("prior_vc");
  return changed;
}

function matchTellMeAbout(text: string, founders: Founder[]) {
  const lower = text.toLowerCase();
  const match = founders.find((f) => lower.includes(f.name.toLowerCase()));
  return match ?? null;
}

export function AskFirstCheckConsole({
  open,
  onOpenChange,
  founders,
}: AskFirstCheckConsoleProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [lastParsed, setLastParsed] = useState<ParsedQuery | null>(null);
  const [summary, setSummary] = useState<SummaryState | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const threadRef = useRef<HTMLDivElement | null>(null);
  const QueryIcon = AGENT_ICON["Query Agent"];

  useEffect(() => {
    if (!open) return;
    const handle = window.setInterval(() => {
      setPlaceholderIndex((i: number) => (i + 1) % PLACEHOLDERS.length);
    }, 3800);
    return () => window.clearInterval(handle);
  }, [open]);

  useEffect(() => {
    if (!threadRef.current) return;
    threadRef.current.scrollTo({
      top: threadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length]);

  const placeholder = PLACEHOLDERS[placeholderIndex] ?? PLACEHOLDERS[0];

  async function loadSummary(founder: Founder) {
    setSummaryLoading(true);
    try {
      const res = await fetch(`/api/founders/${founder.id}`);
      if (!res.ok) return;
      const data = (await res.json()) as { founder: Founder; profile: FounderProfile };
      setSummary({ founder: data.founder, profile: data.profile });
    } finally {
      setSummaryLoading(false);
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setMessages((prev: ChatMessage[]) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", text: trimmed },
    ]);
    setInput("");

    const availableFounders = founders ?? [];
    const tellMatch = matchTellMeAbout(trimmed, availableFounders);
    if (tellMatch) {
      await loadSummary(tellMatch);
      return;
    }

    setSending(true);
    try {
      const refine = !!lastParsed && isRefinement(trimmed);
      const stripped = stripRefinePrefix(trimmed) || trimmed;
      const nextParsed = parseQueryClient(stripped);
      const merged = lastParsed ? mergeParsed(lastParsed, nextParsed) : nextParsed;
      const query = refine
        ? [parsedToQuery(merged), stripped].filter(Boolean).join(", ")
        : trimmed;

      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: query }),
      });
      const data = (await res.json()) as {
        q: string;
        parsed: ParsedQuery;
        results: QueryResult[];
      };

      const changedKeys = refine ? diffParsed(lastParsed, data.parsed) : [];
      setMessages((prev: ChatMessage[]) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "agent",
          query: data.q,
          parsed: data.parsed,
          results: data.results,
          refinement: refine
            ? { previous: lastParsed, changedKeys }
            : undefined,
        },
      ]);
      setLastParsed(data.parsed);
    } finally {
      setSending(false);
    }
  }

  const hasMessages = messages.length > 0;

  return (
    <div
      className={
        "fixed inset-y-0 right-0 z-30 w-full max-w-[420px] transition-transform duration-300 sm:w-[420px] " +
        (open ? "translate-x-0" : "translate-x-full")
      }
      aria-hidden={!open}
    >
      <div className="flex h-full flex-col border-l border-[var(--ink)]/10 bg-[var(--paper)] shadow-[0_30px_80px_-50px_rgba(10,15,30,0.55)]">
        <div className="flex items-center justify-between border-b border-[var(--ink)]/10 px-5 py-4">
          <div>
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
              <QueryIcon size={11} strokeWidth={1.75} aria-hidden />
              <span>query agent</span>
            </div>
            <div className="mt-1 font-display text-lg font-semibold text-[var(--ink)]">
              Ask FirstCheck
            </div>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-full border border-[var(--ink)]/10 bg-white/70 px-3 py-1 text-[11px] uppercase tracking-widest text-[var(--ink)]/70"
          >
            close
          </button>
        </div>

        <div className="flex-1 overflow-hidden">
          <div ref={threadRef} className="flex h-full flex-col gap-3 overflow-y-auto px-5 py-4">
            {!hasMessages && (
              <div className="rounded-2xl border border-dashed border-[var(--ink)]/15 bg-[var(--paper)] p-4">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                  example queries
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {EXAMPLE_QUERIES.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setInput(q)}
                      className="rounded-sm border border-[var(--signal)]/35 bg-[var(--signal)]/5 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m: ChatMessage) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] px-4 py-2 text-sm text-[var(--ink)]">
                    {m.text}
                  </div>
                </div>
              ) : (
                <AgentMessageCard
                  key={m.id}
                  message={m}
                  expanded={expanded}
                  onToggle={(id) =>
                    setExpanded((cur: string | null) => (cur === id ? null : id))
                  }
                  onSelectFounder={(founder) => loadSummary(founder)}
                />
              ),
            )}
          </div>
        </div>

        <div className="border-t border-[var(--ink)]/10 bg-[var(--paper)] px-5 pb-5 pt-3">
          {summary && (
            <div className="mb-4 rounded-2xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_16px_44px_-36px_rgba(20,28,52,0.55)]">
              <div className="flex items-center justify-between">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
                    Summary - compiled from existing profile data
                  </div>
                <button
                  type="button"
                  onClick={() => setSummary(null)}
                  className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55"
                >
                  dismiss
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <div className="font-display text-lg font-semibold text-[var(--ink)]">
                  {summary.profile.headline}
                </div>
                <OriginTag origin={summary.founder.origin} />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
                <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3">
                  <div className="flex items-center justify-between">
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                      founder score
                    </div>
                    <TrendArrow trend={summary.founder.trend} />
                  </div>
                  <div className="mt-2">
                    <UncertaintyBand
                      score={summary.founder.score}
                      band={summary.founder.band}
                      compact
                    />
                  </div>
                </div>
                <div className="rounded-xl border border-[var(--ink)]/10 bg-[var(--paper)] p-3">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
                    top signals
                  </div>
                  <ul className="mt-2 space-y-1 text-xs text-[var(--ink)]/65">
                    {summary.founder.top_signals.slice(0, 3).map((s) => (
                      <li key={s} className="flex gap-2">
                        <span className="mt-[6px] h-[3px] w-[3px] rounded-full bg-[var(--ink)]/35" />
                        <span className="truncate">{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {summaryLoading && (
            <div className="mb-3 rounded-2xl border border-[var(--ink)]/10 bg-[var(--paper)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
              loading summary...
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            className="flex items-center gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              className="flex-1 rounded-2xl border border-[var(--glass-border)] bg-[var(--glass)] px-4 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--ink)]/35 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="rounded-2xl border border-[var(--signal)]/40 bg-[var(--signal)] px-4 py-2 text-xs font-semibold uppercase tracking-widest text-[var(--paper)] shadow-[0_12px_24px_-14px_rgba(61,90,254,0.7)] disabled:opacity-40"
            >
              {sending ? "..." : "send"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function AgentMessageCard({
  message,
  expanded,
  onToggle,
  onSelectFounder,
}: {
  message: Extract<ChatMessage, { role: "agent" }>;
  expanded: string | null;
  onToggle: (id: string) => void;
  onSelectFounder: (founder: Founder) => void;
}) {
  const Icon = AGENT_ICON["Query Agent"];
  const chips = parsedToChips(message.parsed);
  const prevChips = message.refinement?.previous
    ? parsedToChips(message.refinement.previous)
    : [];
  const changed = new Set(message.refinement?.changedKeys ?? []);
  const hasRefinement = !!message.refinement;

  return (
    <div className="rounded-2xl border border-[var(--ink)]/10 bg-[var(--paper)] p-4 shadow-[0_18px_40px_-34px_rgba(24,33,70,0.45)]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          <Icon size={11} strokeWidth={1.75} aria-hidden />
          Query Agent read this as:
        </span>
        {chips.length === 0 ? (
          <span className="font-mono text-[11px] text-[var(--ink)]/45">
            no structured fields resolved - falling back to fuzzy match
          </span>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={`${message.id}-${c.k}`}
                className="rounded-sm border border-[var(--signal)]/50 bg-[var(--signal)]/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]"
              >
                {c.k} = {c.v}
              </span>
            ))}
          </div>
        )}
      </div>

      {hasRefinement && prevChips.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
            previous:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {prevChips.map((c) => (
              <span
                key={`${message.id}-prev-${c.k}`}
                className={
                  "rounded-sm border border-[var(--ink)]/15 bg-[var(--paper)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/60 " +
                  (changed.has(c.k) ? "line-through" : "")
                }
              >
                {c.k} = {c.v}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 grid gap-2">
        {message.results.length === 0 ? (
          <div className="rounded-md border border-dashed border-[var(--ink)]/15 bg-[var(--paper)] p-4 text-center">
            <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
              no matches
            </div>
            <p className="mt-2 text-xs text-[var(--ink)]/70">
              No founder in the ledger matches this query.
            </p>
          </div>
        ) : (
          message.results.map((r) => (
            <FounderResultCard
              key={r.founder.id}
              result={r}
              expanded={expanded === r.founder.id}
              onToggle={() => onToggle(r.founder.id)}
              onSelect={() => onSelectFounder(r.founder)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function FounderResultCard({
  result,
  expanded,
  onToggle,
  onSelect,
}: {
  result: QueryResult;
  expanded: boolean;
  onToggle: () => void;
  onSelect: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cardId = `chat-result-${result.founder.id}`;
  const evidenceIds = result.why_matched.map(
    (w, idx) => `chat-evidence-${result.founder.id}-${idx}`,
  );

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => {
          onToggle();
          onSelect();
        }}
        className={
          "w-full rounded-2xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-3 text-left shadow-[0_14px_34px_-28px_rgba(24,33,70,0.45)] transition-transform hover:-translate-y-0.5 " +
          (expanded ? "border-[var(--signal)]/35" : "")
        }
      >
        <div id={cardId} className="flex flex-wrap items-center gap-2">
          <div className="font-display text-base font-semibold text-[var(--ink)]">
            {result.founder.name}
          </div>
          <OriginTag origin={result.founder.origin} />
          <div className="flex items-center gap-1 rounded-full border border-[var(--ink)]/10 bg-white/70 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/70">
            {result.founder.score} +/- {result.founder.band}
            <TrendArrow trend={result.founder.trend} />
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {result.why_matched.slice(0, 2).map((w) => (
            <span
              key={w}
              className="rounded-sm border border-[var(--signal)]/50 bg-[var(--signal)]/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]"
            >
              {w}
            </span>
          ))}
        </div>
      </button>

      {expanded && result.why_matched.length > 0 && (
        <div className="mt-3 rounded-2xl border border-dashed border-[var(--ink)]/15 bg-[var(--paper)] p-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
            evidence trail
          </div>
          <ul className="mt-2 space-y-2 text-xs text-[var(--ink)]/65">
            {result.why_matched.map((w, idx) => (
              <li
                key={`${w}-${idx}`}
                id={evidenceIds[idx]}
                className="flex items-start gap-2"
              >
                <span className="mt-[6px] h-[3px] w-[3px] rounded-full bg-[var(--signal)]" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
          {evidenceIds.map((eid) => (
            <EvidenceThread
              key={eid}
              fromId={cardId}
              toId={eid}
              status="supported"
              container={containerRef}
            />
          ))}
        </div>
      )}
    </div>
  );
}
