import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import type { Founder } from "@/lib/dashboard-data";
import { OriginTag, TrendArrow, UncertaintyBand } from "@/components/ds";

export const Route = createFileRoute("/founder")({
  component: FounderIndex,
});

function FounderIndex() {
  const [founders, setFounders] = useState<Founder[] | null>(null);

  useEffect(() => {
    fetch("/api/dashboard")
      .then((r) => r.json())
      .then((d) => setFounders(d.founders ?? []));
  }, []);

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-10 md:px-10 md:py-12">
      <header className="fancy-card relative overflow-hidden rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-hero)] p-6 shadow-[0_40px_90px_-70px_rgba(27,37,94,0.8)] md:p-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(520px_240px_at_10%_-10%,rgba(61,90,254,0.22),transparent_60%)]" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(520px_240px_at_90%_-10%,rgba(56,189,248,0.18),transparent_60%)]" />
        <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent)] px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/70">
          founder · memory index
        </div>
        <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight text-[var(--ink)] md:text-4xl">
          Founder memory
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink)]/60">
          The founder is the primary key. Pick one to open their full evidence
          timeline, score history, and applications.
        </p>
        <div className="mt-4 grid gap-3 rounded-2xl border border-[var(--glass-border)] bg-[var(--glass)] p-4 shadow-[0_24px_60px_-50px_rgba(27,37,94,0.7)] backdrop-blur md:grid-cols-3">
          <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
              total founders
            </div>
            <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
              {founders ? founders.length : "—"}
            </div>
          </div>
          <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
              open apps
            </div>
            <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
              {founders ? founders.filter((f) => f.has_open_app).length : "—"}
            </div>
          </div>
          <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-strong)] p-3">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
              avg score
            </div>
            <div className="mt-1 font-display text-2xl font-semibold text-[var(--ink)]">
              {founders && founders.length
                ? Math.round(founders.reduce((s, f) => s + f.score, 0) / founders.length)
                : "—"}
            </div>
          </div>
        </div>
      </header>

      <div className="mt-6 flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
          founder · score · origin · signals
        </div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
          confidence
        </div>
      </div>

      <ul className="mt-3 space-y-3">
        {(founders ?? []).map((f) => (
          <li key={f.id}>
            <Link
              to="/founder/$id"
              params={{ id: f.id }}
              className="fancy-card gradient-border glow-card group flex items-center justify-between gap-4 rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 text-[var(--ink)] shadow-[0_26px_60px_-52px_rgba(24,33,70,0.7)] transition-transform hover:-translate-y-[2px]"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="min-w-0">
                  <div className="font-display text-base font-semibold tracking-tight">
                    {f.name}
                  </div>
                  <div className="font-mono text-[11px] text-[var(--ink)]/55">
                    {f.handle}
                  </div>
                </div>
                <OriginTag origin={f.origin} />
                {f.has_open_app && (
                  <span className="rounded-full border border-[var(--signal)]/30 bg-[var(--surface-accent)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[var(--signal)]">
                    open app
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <div className="w-[120px]">
                  <UncertaintyBand score={f.score} band={f.band} />
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="font-mono text-2xl tabular-nums leading-none">
                    {f.score}
                  </span>
                  <TrendArrow trend={f.trend} />
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
