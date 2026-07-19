import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

type AppListItem = {
  id: string;
  company: string;
  founder_name: string;
  founder_id: string;
  submitted_at: string;
  progress: number;
};

export const Route = createFileRoute("/application/")({
  component: ApplicationIndex,
});

function ApplicationIndex() {
  const [apps, setApps] = useState<AppListItem[] | null>(null);

  useEffect(() => {
    fetch("/api/applications")
      .then((r) => r.json())
      .then((d: { applications: AppListItem[] }) => setApps(d.applications));
  }, []);

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-10 sm:px-6 md:px-10">
      <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--ink)]/45">
        application
      </div>
      <h1 className="mt-1 font-display text-3xl font-medium tracking-tight">
        Open applications
      </h1>
      <p className="mt-2 max-w-lg text-sm text-[var(--ink)]/60">
        Every application runs the same five-stage pipeline: claims → screen →
        diligence → memo → devil's advocate. Open one to see the state of each
        stage.
      </p>

      <ul className="mt-8 space-y-2">
        {apps === null ? (
          <li className="h-20 animate-pulse rounded-md bg-[var(--ink)]/[0.06]" />
        ) : apps.length === 0 ? (
          <li className="fancy-card gradient-border rounded-2xl border border-dashed border-[var(--ink)]/15 bg-[var(--surface-card-soft)] p-6 text-sm text-[var(--ink)]/60">
            No applications yet. Upload a deck from a founder profile to begin.
          </li>
        ) : (
          apps.map((a) => (
            <li key={a.id}>
              <Link
                to="/application/$id"
                params={{ id: a.id }}
                className="fancy-card gradient-border glow-card block rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-5 text-[var(--ink)] shadow-[0_28px_70px_-60px_rgba(24,33,70,0.7)] transition-transform hover:-translate-y-[2px]"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-display text-lg font-semibold tracking-tight">
                      {a.company}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-[var(--ink)]/55">
                      {a.founder_name} · submitted{" "}
                      {new Date(a.submitted_at).toISOString().slice(0, 10)} ·{" "}
                      {a.id}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <span
                        key={i}
                        aria-hidden
                        className="h-1.5 w-8 rounded-full"
                        style={{
                          background:
                            i < a.progress
                              ? "var(--verified)"
                              : "color-mix(in oklab, var(--ink) 15%, transparent)",
                        }}
                      />
                    ))}
                    <span className="ml-2 font-mono text-[11px] text-[var(--ink)]/55">
                      {a.progress}/5
                    </span>
                  </div>
                </div>
              </Link>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
