import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type NavItem = {
  label: string;
  to: string;
  hint?: string;
};

const NAV: NavItem[] = [
  { label: "Dashboard", to: "/", hint: "sourced founders" },
  { label: "Founder", to: "/founder", hint: "profile & memory" },
  { label: "Application", to: "/application", hint: "claims → memo" },
  { label: "Decision queue", to: "/queue", hint: "human gate" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const activeNav = NAV.find((item) =>
    item.to === "/"
      ? pathname === "/"
      : pathname === item.to || pathname.startsWith(item.to + "/"),
  );

  useEffect(() => {
    const stored = window.localStorage.getItem("theme");
    const prefersDark =
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    const next = stored === "light" || stored === "dark"
      ? stored
      : prefersDark
        ? "dark"
        : "light";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    window.localStorage.setItem("theme", next);
  };

  return (
    <div className="dashboard-density flex min-h-screen w-full bg-[var(--background)] text-[var(--ink)]">
      {/* Persistent left rail — light ClickUp-like navigation */}
      <aside
        className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-[var(--sidebar-border)] bg-[var(--sidebar)] text-[var(--sidebar-foreground)] md:flex"
        aria-label="Primary"
      >
        <div className="px-5 pb-6 pt-6">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--sidebar-foreground)]/55">
            workspace
          </div>
          <div className="mt-1 font-display text-sm font-semibold tracking-tight text-[var(--sidebar-foreground)]">
            Review console
          </div>
        </div>

        <nav className="flex-1 px-2">
          <ul className="space-y-0.5">
            {NAV.map((item) => {
              const active =
                item.to === "/"
                  ? pathname === "/"
                  : pathname === item.to || pathname.startsWith(item.to + "/");
              return (
                <li key={item.to} className="relative">
                  {active && (
                    <span
                      aria-hidden
                      className="absolute left-1 top-1.5 bottom-1.5 w-[3px] rounded-full"
                      style={{ background: "var(--signal)" }}
                    />
                  )}
                  <Link
                    to={item.to}
                    className={cn(
                      "block rounded-xl px-3 py-2.5 pl-5 transition-colors duration-150",
                      active
                        ? "bg-[var(--sidebar-accent)] text-[var(--sidebar-foreground)] shadow-[0_12px_24px_-18px_rgba(61,90,254,0.45)]"
                        : "text-[var(--sidebar-foreground)]/70 hover:bg-[color-mix(in_oklab,var(--sidebar-accent)_60%,transparent)] hover:text-[var(--sidebar-foreground)]",
                    )}
                  >
                    <div className="text-sm font-medium tracking-tight">
                      {item.label}
                    </div>
                    {item.hint && (
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--sidebar-foreground)]/45">
                        {item.hint}
                      </div>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="px-5 pb-5 pt-4">
          <div className="rounded-xl border border-[var(--sidebar-border)] bg-white p-3">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--sidebar-foreground)]/55">
              build
            </div>
            <div className="mt-1 font-mono text-[11px] text-[var(--sidebar-foreground)]/70">
              v0.1.0 · design system
            </div>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="mt-3 w-full rounded-full border border-[var(--sidebar-border)] bg-[var(--sidebar-accent)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--sidebar-foreground)]/80 transition-colors hover:text-[var(--sidebar-foreground)]"
          >
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="sticky top-0 z-30 border-b border-[var(--ink)]/10 bg-[var(--glass)] backdrop-blur">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6 md:px-10">
            <div className="min-w-0">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/50">
                workspace
              </div>
              <div className="truncate font-display text-lg font-semibold text-[var(--ink)]">
                {activeNav?.label ?? "Overview"}
              </div>
            </div>
            <div className="hidden flex-1 items-center justify-center md:flex">
              <div className="flex w-full max-w-[420px] items-center gap-2 rounded-full border border-[var(--ink)]/10 bg-[var(--glass)] px-3 py-2 text-[13px] text-[var(--ink)]/60 shadow-[0_16px_40px_-32px_rgba(24,33,70,0.45)]">
                <span className="h-2 w-2 rounded-full bg-[var(--signal)]" aria-hidden />
                <span className="truncate">Search founders, applications, signals…</span>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:justify-end">
              <button
                type="button"
                className="rounded-full border border-[var(--ink)]/10 bg-[var(--paper)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/70 shadow-[0_12px_28px_-20px_rgba(24,33,70,0.45)]"
              >
                new
              </button>
              <button
                type="button"
                className="rounded-full border border-[var(--ink)]/10 bg-[var(--paper)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/70"
              >
                invite
              </button>
              <div className="h-9 w-9 rounded-full border border-[var(--ink)]/10 bg-[var(--surface-card)]" />
            </div>
          </div>
        </div>
        <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 px-4 pb-10 sm:px-6 md:px-10 lg:flex-row lg:gap-6">
          <div className="min-w-0 flex-1">
            {children}
          </div>
          <aside className="hidden w-[300px] shrink-0 lg:block">
            <RightSidebar pathname={pathname} />
          </aside>
        </div>
      </main>
    </div>
  );
}

function RightSidebar({ pathname }: { pathname: string }) {
  const [state, setState] = useState<
    | { kind: "dashboard" | "founder-list"; founders: Array<any> }
    | { kind: "founder-detail"; profile: any }
    | { kind: "application-list"; applications: Array<any> }
    | { kind: "application-detail"; application: any }
    | { kind: "queue"; queue: Array<any>; metrics: any }
    | { kind: "loading" }
  >({ kind: "loading" });

  useEffect(() => {
    const segments = pathname.split("/").filter(Boolean);
    const isFounderDetail = segments[0] === "founder" && segments[1];
    const isApplicationDetail = segments[0] === "application" && segments[1];
    const isApplicationList = pathname.startsWith("/application") && !isApplicationDetail;
    const isFounderList = pathname.startsWith("/founder") && !isFounderDetail;
    const isQueue = pathname.startsWith("/queue");
    const fetchData = async () => {
      setState({ kind: "loading" });
      if (isQueue) {
        const [queueRes, metricsRes] = await Promise.all([
          fetch("/api/decisions/queue"),
          fetch("/api/metrics"),
        ]);
        const queueJson = await queueRes.json();
        const metricsJson = await metricsRes.json();
        setState({ kind: "queue", queue: queueJson.queue ?? [], metrics: metricsJson });
        return;
      }
      if (isFounderDetail) {
        const id = segments[1];
        const res = await fetch(`/api/founders/${id}`);
        const json = await res.json();
        setState({ kind: "founder-detail", profile: json });
        return;
      }
      if (isApplicationDetail) {
        const id = segments[1];
        const res = await fetch(`/api/applications/${id}`);
        const json = await res.json();
        setState({ kind: "application-detail", application: json });
        return;
      }
      if (isApplicationList) {
        const res = await fetch("/api/applications");
        const json = await res.json();
        setState({ kind: "application-list", applications: json.applications ?? [] });
        return;
      }
      const res = await fetch("/api/dashboard");
      const json = await res.json();
      setState({ kind: "dashboard", founders: json.founders ?? [] });
    };
    fetchData().catch(() => setState({ kind: "loading" }));
  }, [pathname]);

  return (
    <div className="sticky top-[84px] flex flex-col gap-4">
      {state.kind === "loading" && (
        <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            loading sidebar…
          </div>
        </div>
      )}

      {(state.kind === "dashboard" || state.kind === "founder-list") && (
        <DashboardSidebar founders={state.founders} />
      )}
      {state.kind === "founder-detail" && (
        <FounderSidebar profile={state.profile} />
      )}
      {state.kind === "application-list" && (
        <ApplicationListSidebar applications={state.applications} />
      )}
      {state.kind === "application-detail" && (
        <ApplicationSidebar application={state.application} />
      )}
      {state.kind === "queue" && (
        <QueueSidebar queue={state.queue} metrics={state.metrics} />
      )}
    </div>
  );
}

function DashboardSidebar({ founders }: { founders: Array<any> }) {
  const total = founders.length;
  const openApps = founders.filter((f) => f.has_open_app).length;
  const synthetic = founders.filter((f) => f.origin === "synthetic").length;
  const avgScore = total
    ? Math.round(founders.reduce((sum, f) => sum + f.score, 0) / total)
    : 0;
  const topFounders = [...founders]
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
  const originCounts = [
    { label: "github", value: founders.filter((f) => f.origin === "github").length },
    { label: "hn", value: founders.filter((f) => f.origin === "hn").length },
    { label: "inbound", value: founders.filter((f) => f.origin === "inbound").length },
    { label: "synthetic", value: synthetic },
  ];
  const scoreBands = Array.from({ length: 5 }, () => 0);
  founders.forEach((f) => {
    const idx = Math.min(4, Math.floor(f.score / 20));
    scoreBands[idx] += 1;
  });
  const scoreTrend = founders.slice(0, 14).map((f) => f.score).reverse();
  return (
    <>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          week at a glance
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <StatMini label="founders" value={String(total)} />
          <StatMini label="open apps" value={String(openApps)} />
          <StatMini label="synthetic" value={String(synthetic)} />
          <StatMini label="avg score" value={String(avgScore)} />
        </div>
      </div>

      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            score distribution
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">0–100</span>
        </div>
        <MiniHistogram data={scoreBands} />
      </div>

      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            score momentum
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">recent</span>
        </div>
        <MiniLineChart points={scoreTrend} />
      </div>

      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            origin mix
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">current</span>
        </div>
        <MiniBarChart data={originCounts} />
      </div>

      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          top founders
        </div>
        <ul className="mt-3 space-y-2">
          {topFounders.map((f) => (
            <li key={f.id}>
              <Link
                to="/founder/$id"
                params={{ id: f.id }}
                className="flex items-center justify-between rounded-2xl border border-[var(--ink)]/10 bg-[var(--glass-strong)] px-3 py-2 text-[12px] text-[var(--ink)]/80"
              >
                <span className="truncate font-display font-medium text-[var(--ink)]">
                  {f.name}
                </span>
                <span className="font-mono text-[11px] text-[var(--ink)]/50">
                  {f.score}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

function FounderSidebar({ profile }: { profile: any }) {
  const founder = profile?.founder;
  const data = profile?.profile;
  const scoreSeries = data?.score_history?.map((d: any) => d.score) ?? [];
  return (
    <>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          founder stats
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <StatMini label="score" value={String(founder?.score ?? "—")} />
          <StatMini label="band" value={String(founder?.band ?? "—")} />
          <StatMini label="signals" value={String(data?.signals?.length ?? 0)} />
          <StatMini label="apps" value={String(data?.applications?.length ?? 0)} />
        </div>
      </div>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            score history
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">90d</span>
        </div>
        <MiniLineChart points={scoreSeries} />
      </div>
    </>
  );
}

function ApplicationListSidebar({ applications }: { applications: Array<any> }) {
  const total = applications.length;
  const avgProgress = total
    ? Math.round(applications.reduce((sum, a) => sum + a.progress, 0) / total)
    : 0;
  const recent = applications.filter((a) => {
    const d = new Date(a.submitted_at).getTime();
    return Date.now() - d < 1000 * 60 * 60 * 24 * 7;
  }).length;
  const progressBuckets = [0, 0, 0, 0, 0];
  applications.forEach((a) => {
    const idx = Math.min(4, Math.max(0, a.progress - 1));
    progressBuckets[idx] += 1;
  });
  const progressData = progressBuckets.map((v, i) => ({
    label: `s${i + 1}`,
    value: v,
  }));
  return (
    <>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          application stats
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <StatMini label="open" value={String(total)} />
          <StatMini label="avg stage" value={`${avgProgress}/5`} />
          <StatMini label="last 7d" value={String(recent)} />
          <StatMini label="progress" value={`${Math.round((avgProgress / 5) * 100)}%`} />
        </div>
      </div>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            pipeline stages
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">distribution</span>
        </div>
        <MiniBarChart data={progressData} />
      </div>
    </>
  );
}

function ApplicationSidebar({ application }: { application: any }) {
  const stage = application?.stage ?? {};
  const completed = Object.values(stage).filter((s) => s === "complete").length;
  const claims = application?.claims?.length ?? 0;
  const signals = application?.diligence?.signals?.length ?? 0;
  const contradictions = application?.diligence?.signals?.filter((s: any) => (s.contradicts ?? []).length).length ?? 0;
  const stageData = [
    { label: "claims", value: stage.claims === "complete" ? 1 : 0 },
    { label: "screen", value: stage.screen === "complete" ? 1 : 0 },
    { label: "dilig", value: stage.diligence === "complete" ? 1 : 0 },
    { label: "memo", value: stage.memo === "complete" ? 1 : 0 },
    { label: "adv", value: stage.adversary === "complete" ? 1 : 0 },
  ];
  return (
    <>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          application stats
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <StatMini label="claims" value={String(claims)} />
          <StatMini label="signals" value={String(signals)} />
          <StatMini label="stages" value={`${completed}/5`} />
          <StatMini label="contradict" value={String(contradictions)} />
        </div>
      </div>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            stage completion
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">state</span>
        </div>
        <MiniBarChart data={stageData} compact />
      </div>
    </>
  );
}

function QueueSidebar({ queue, metrics }: { queue: Array<any>; metrics: any }) {
  const total = queue.length;
  const invest = queue.filter((q) => q.recommendation?.verdict === "invest").length;
  const pass = queue.filter((q) => q.recommendation?.verdict === "pass").length;
  const revisit = queue.filter((q) => q.recommendation?.verdict === "revisit").length;
  const funnel = metrics?.funnel ?? {};
  const stageData = [
    { label: "src", value: funnel.sourced ?? 0 },
    { label: "scr", value: funnel.screened ?? 0 },
    { label: "dil", value: funnel.diligenced ?? 0 },
    { label: "dec", value: funnel.decided ?? 0 },
  ];
  return (
    <>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
          queue stats
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <StatMini label="pending" value={String(total)} />
          <StatMini label="invest" value={String(invest)} />
          <StatMini label="pass" value={String(pass)} />
          <StatMini label="revisit" value={String(revisit)} />
        </div>
      </div>
      <div className="fancy-card rounded-3xl border border-[var(--ink)]/10 bg-[var(--surface-card-soft)] p-4 shadow-[0_24px_60px_-50px_rgba(24,33,70,0.6)]">
        <div className="flex items-center justify-between">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            funnel snapshot
          </div>
          <span className="font-mono text-[10px] text-[var(--ink)]/45">current</span>
        </div>
        <MiniBarChart data={stageData} compact />
      </div>
    </>
  );
}

function StatMini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--ink)]/10 bg-[var(--glass-strong)] px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/45">
        {label}
      </div>
      <div className="mt-1 font-display text-lg font-semibold text-[var(--ink)]">
        {value}
      </div>
    </div>
  );
}

function MiniLineChart({ points }: { points: number[] }) {
  if (!points || points.length < 2) {
    return (
      <div className="mt-3 h-12 rounded-xl border border-[var(--ink)]/10 bg-[var(--glass-strong)]" />
    );
  }
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = Math.max(1, max - min);
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * 120;
      const y = 36 - ((p - min) / span) * 28;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="mt-3">
      <svg viewBox="0 0 120 40" className="h-12 w-full" aria-label="Pipeline throughput">
        <path d={path} fill="none" stroke="var(--signal)" strokeWidth="2" />
        <path d={`${path} L 120 40 L 0 40 Z`} fill="var(--signal)" opacity="0.12" />
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--ink)]/45">
        <span>start</span>
        <span>now</span>
      </div>
    </div>
  );
}

function MiniBarChart({
  data,
  compact = false,
}: {
  data: Array<{ label: string; value: number }>;
  compact?: boolean;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={compact ? "mt-3 space-y-1.5" : "mt-3 space-y-2"}>
      {data.map((row) => (
        <div key={row.label} className="flex items-center gap-2">
          <span className="w-16 font-mono text-[10px] uppercase tracking-widest text-[var(--ink)]/55">
            {row.label}
          </span>
          <div className="flex-1">
            <div
              className="h-2 rounded-full bg-[var(--signal)]/70"
              style={{ width: `${(row.value / max) * 100}%` }}
            />
          </div>
          <span className="w-6 text-right font-mono text-[10px] text-[var(--ink)]/45">
            {row.value}
          </span>
        </div>
      ))}
    </div>
  );
}

function MiniHistogram({ data }: { data: number[] }) {
  const max = Math.max(1, ...data);
  return (
    <div className="mt-3">
      <svg viewBox="0 0 120 36" className="h-10 w-full" aria-label="Score distribution">
        {data.map((v, i) => {
          const h = (v / max) * 26;
          const x = i * 22 + 6;
          const y = 30 - h;
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
        <path d="M2 30 H118" stroke="rgba(31,36,48,0.12)" strokeWidth="1" />
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-[var(--ink)]/45">
        <span>0–19</span>
        <span>80–100</span>
      </div>
    </div>
  );
}
