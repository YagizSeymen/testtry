"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BadgeCheck,
  Bot,
  Check,
  ChevronRight,
  Clock3,
  ClipboardCheck,
  Database,
  FileText,
  Flame,
  LayoutDashboard,
  LoaderCircle,
  Mail,
  PanelRightOpen,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  Target,
  UserRound,
  X
} from "lucide-react";

type Founder = {
  founder_id: string;
  name: string;
  origin: string;
  founder_score: number;
  band: number;
  trend: "up" | "flat" | "down";
  top_signals: string[];
  has_open_app: boolean;
};

type Signal = { signal_id: string; ts: string; source: string; text: string; url: string | null };
type Claim = { claim_id: string; type: string; text: string; source_span: string | null };
type Profile = {
  profile: { founder_id: string; name: string; headline: string | null; location: string | null; origin: string; bio: string | null };
  signals: Signal[];
  score_history: { ts: string; score: number; band: number }[];
  applications: string[];
};
type Axes = {
  founder: { score: number; trend: string; rationale: string };
  market: { rating: string; rationale: string };
  idea_vs_market: { verdict: string; rationale: string };
};
type Application = {
  application_id: string;
  founder_id: string;
  company_name: string;
  status: string;
  claims: Claim[];
  axes: Axes | null;
  diligence: { claims: { claim_id: string; verdict: string; trust: string; evidence: string[]; note: string }[]; gaps: string[] } | null;
  memo: { memo_id: string; sections: Record<string, string>; recommendation: { invest: boolean; amount: number; rationale: string; based_on: string[] } } | null;
  adversarial: { persona: string; objections: { text: string; targets: string[]; evidence: string[] | null; label: string; verification: string }[] } | null;
  decision_brief: { summary: string; contested: { claim_id: string; objection_i: number; severity: string }[]; stats: { claims: number; contested: number; verified_attacks: number } } | null;
  evidence: Signal[];
};
type Recommendation = { invest: boolean; amount: number; rationale: string; based_on: string[] };
type QueueItem = { application_id: string; company: string; recommendation: Recommendation; memo_id: string };
type Thesis = { sectors: string[]; stage: string; geo: string[]; check_size: number; risk_appetite: string };
type Metrics = { signal_to_decision_min: number | null; funnel: { sourced: number; screened: number; diligenced: number; decided: number } };
type LatencySample = { label: string; ms: number; ok: boolean };
type ScanRun = { new_founders: number; new_signals: number; candidates_found: number; candidates_reviewed: number; cached: boolean };

const DEMO_DECK = `Founder: Maya Chen
NeuralKit has reached $50K in monthly recurring revenue.
Our initial customers are AI infrastructure teams.
We shipped a model observability platform for ML teams.
Cap table information is not included in this deck.`;

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "The request could not be completed.");
  return body as T;
}

const displayDate = (value: string) => new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));
const initials = (name: string) => name.split(" ").map((part) => part[0]).slice(0, 2).join("");

function Trend({ value }: { value: Founder["trend"] }) {
  if (value === "up") return <span className="trend up"><ArrowUpRight size={14} /> improving</span>;
  if (value === "down") return <span className="trend down"><ArrowDownRight size={14} /> declining</span>;
  return <span className="trend flat"><Activity size={13} /> stable</span>;
}

function StageDot({ ready, label }: { ready: boolean; label: string }) {
  return <div className={`stage-dot ${ready ? "ready" : ""}`}><span>{ready ? <Check size={12} /> : ""}</span>{label}</div>;
}

export default function ProductPage() {
  const [view, setView] = useState<"dashboard" | "founder" | "application" | "decisions">("dashboard");
  const [founders, setFounders] = useState<Founder[]>([]);
  const [selectedFounder, setSelectedFounder] = useState<Founder | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [thesis, setThesis] = useState<Thesis | null>(null);
  const [search, setSearch] = useState("");
  const [searchIds, setSearchIds] = useState<string[] | null>(null);
  const [searchChips, setSearchChips] = useState<string[]>([]);
  const [outreach, setOutreach] = useState<string | null>(null);
  const [showSubmission, setShowSubmission] = useState(false);
  const [showThesis, setShowThesis] = useState(false);
  const [scanRun, setScanRun] = useState<ScanRun | null>(null);
  const [companyName, setCompanyName] = useState("NeuralKit");
  const [deckText, setDeckText] = useState(DEMO_DECK);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latencies, setLatencies] = useState<LatencySample[]>([]);

  const displayedFounders = useMemo(() => searchIds ? founders.filter((founder) => searchIds.includes(founder.founder_id)) : founders, [founders, searchIds]);

  async function timedApi<T>(label: string, path: string, options?: RequestInit): Promise<T> {
    const startedAt = performance.now();
    let ok = true;
    try {
      return await api<T>(path, options);
    } catch (cause) {
      ok = false;
      throw cause;
    } finally {
      const sample = { label, ms: performance.now() - startedAt, ok };
      setLatencies((previous) => [sample, ...previous].slice(0, 12));
    }
  }

  const refresh = async () => {
    const [dashboard, thesisResult, metricsResult, queueResult] = await Promise.all([
      api<Founder[]>("/dashboard"),
      api<{ thesis: Thesis }>("/thesis"),
      api<Metrics>("/metrics"),
      api<QueueItem[]>("/decisions/queue")
    ]);
    setFounders(dashboard);
    setThesis(thesisResult.thesis);
    setMetrics(metricsResult);
    setQueue(queueResult);
    if (!selectedFounder && dashboard[0]) void chooseFounder(dashboard[0], false);
  };

  useEffect(() => { void refresh().catch((cause) => setError(cause.message)); }, []);

  async function chooseFounder(founder: Founder, goToProfile = true) {
    setBusy("founder");
    try {
      const nextProfile = await api<Profile>(`/founders/${founder.founder_id}`);
      setSelectedFounder(founder);
      setProfile(nextProfile);
      setOutreach(null);
      if (goToProfile) setView("founder");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load founder.");
    } finally {
      setBusy(null);
    }
  }

  async function runScan() {
    setBusy("scan"); setError(null);
    try {
      const result = await timedApi<ScanRun>("Live scan", "/scan/run", { method: "POST", body: "{}" });
      setScanRun(result);
      await refresh();
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Scan failed."); }
    finally { setBusy(null); }
  }

  async function runSearch(event: FormEvent) {
    event.preventDefault();
    if (!search.trim()) { setSearchIds(null); setSearchChips([]); return; }
    setBusy("search"); setError(null);
    try {
      const result = await timedApi<{ filter: Record<string, unknown>; results: { founder_id: string; why_matched: string[] }[] }>("Query", "/query", { method: "POST", body: JSON.stringify({ q: search }) });
      setSearchIds(result.results.map((item) => item.founder_id));
      setSearchChips(Array.from(new Set(result.results.flatMap((item) => item.why_matched))));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Query failed."); }
    finally { setBusy(null); }
  }

  async function activateFounder() {
    if (!selectedFounder) return;
    setBusy("activate");
    try {
      const result = await api<{ outreach_draft: string }>(`/founders/${selectedFounder.founder_id}/activate`, { method: "POST", body: "{}" });
      setOutreach(result.outreach_draft);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Activation failed."); }
    finally { setBusy(null); }
  }

  async function submitApplication(event: FormEvent) {
    event.preventDefault();
    setBusy("submit"); setError(null);
    try {
      const created = await timedApi<{ application_id: string; founder_id: string }>("Extract", "/applications", { method: "POST", body: JSON.stringify({ company_name: companyName, deck_text: deckText }) });
      const nextApplication = await api<Application>(`/applications/${created.application_id}`);
      const founder = founders.find((item) => item.founder_id === created.founder_id);
      setApplication(nextApplication);
      if (founder) await chooseFounder(founder, false);
      setShowSubmission(false); setView("application"); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Application submission failed."); }
    finally { setBusy(null); }
  }

  async function runStage(stage: "screen" | "diligence" | "memo" | "adversary") {
    if (!application) return;
    setBusy(stage); setError(null);
    try {
      const stageLabels: Record<typeof stage, string> = { screen: "Screen", diligence: "Diligence", memo: "Memo", adversary: "Counter-case" };
      await timedApi(stageLabels[stage], `/applications/${application.application_id}/${stage}`, { method: "POST", body: "{}" });
      setApplication(await api<Application>(`/applications/${application.application_id}`));
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : `Unable to run ${stage}.`); }
    finally { setBusy(null); }
  }

  async function decide(action: "approve" | "reject") {
    if (!application) return;
    setBusy(action); setError(null);
    try {
      await api(`/decisions/${application.application_id}/decide`, { method: "POST", body: JSON.stringify({ action, approver: "Investment Committee" }) });
      setApplication(await api<Application>(`/applications/${application.application_id}`));
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Decision failed."); }
    finally { setBusy(null); }
  }

  async function saveThesis(event: FormEvent) {
    event.preventDefault();
    if (!thesis) return;
    setBusy("thesis");
    try {
      await api("/thesis", { method: "POST", body: JSON.stringify({ thesis }) });
      setShowThesis(false);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Thesis update failed."); }
    finally { setBusy(null); }
  }

  const appNextStage = !application?.axes ? "screen" : !application.diligence ? "diligence" : !application.memo ? "memo" : !application.adversarial ? "adversary" : null;

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Target size={19} /></span><span className="brand-word"><b>FIRST</b><i>//</i>CHECK</span></div>
        <div className="fund-label">Venture intelligence / fc.01</div>
        <nav className="nav-list" aria-label="Primary navigation">
          <button title="Dashboard" className={view === "dashboard" ? "nav-item active" : "nav-item"} onClick={() => setView("dashboard")}><LayoutDashboard size={18} />Dashboard</button>
          <button title="Founder profile" className={view === "founder" ? "nav-item active" : "nav-item"} onClick={() => setView("founder")}><UserRound size={18} />Founder profile</button>
          <button title="Application workbench" className={view === "application" ? "nav-item active" : "nav-item"} onClick={() => setView("application")}><FileText size={18} />Application</button>
          <button title="Decision queue" className={view === "decisions" ? "nav-item active" : "nav-item"} onClick={() => setView("decisions")}><ClipboardCheck size={18} />Decision queue</button>
        </nav>
        <div className="sidebar-footer">
          <span className="live-dot" />Web scan + cache fallback
          <span className="synthetic-key"><i />Source provenance retained</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="title-lockup"><p className="eyebrow">Single-fund workspace</p><h1>{view === "dashboard" ? "Founder discovery" : view === "founder" ? "Founder evidence" : view === "application" ? "Investment workbench" : "Human decision queue"}</h1><div className="workspace-status"><i /><span>{busy === "scan" ? "Web scan running" : scanRun ? scanRun.cached ? "Cache fallback retained" : `Live scan found ${scanRun.candidates_found} candidates` : "Memory synchronized"}</span><span className="status-divider">/</span><span>Fund 01</span></div></div>
          <div className="system-readout" aria-label="System readout"><span>FC.01</span><i /><span>MEM // LIVE</span></div>
          <div className="top-actions">
            <button className="icon-button" title="Run thesis-driven live web scan" onClick={() => void runScan()} disabled={busy === "scan"}>{busy === "scan" ? <LoaderCircle className="spin" size={18} /> : <RefreshCw size={18} />}</button>
            <button className="command-button" onClick={() => setShowSubmission(true)}><Plus size={17} />New application</button>
          </div>
        </header>

        {error && <div className="error-banner"><AlertTriangle size={17} /><span>{error}</span><button className="icon-button compact" title="Dismiss error" onClick={() => setError(null)}><X size={16} /></button></div>}

        {view === "dashboard" && <DashboardView founders={displayedFounders} metrics={metrics} search={search} setSearch={setSearch} searchChips={searchChips} isSearching={busy === "search"} onSearch={runSearch} onClear={() => { setSearch(""); setSearchIds(null); setSearchChips([]); }} onSelect={(founder) => void chooseFounder(founder)} thesis={thesis} onEditThesis={() => setShowThesis(true)} latencies={latencies} scanRun={scanRun} />}
        {view === "founder" && <FounderView founder={selectedFounder} profile={profile} outreach={outreach} busy={busy} onActivate={() => void activateFounder()} onOpenApplication={(id) => { void api<Application>(`/applications/${id}`).then((result) => { setApplication(result); setView("application"); }); }} />}
        {view === "application" && <ApplicationView application={application} nextStage={appNextStage} busy={busy} onRun={(stage) => void runStage(stage)} onDecide={(action) => void decide(action)} onNew={() => setShowSubmission(true)} latencies={latencies} />}
        {view === "decisions" && <DecisionView queue={queue} application={application} onOpen={(id) => { void api<Application>(`/applications/${id}`).then((result) => { setApplication(result); setView("application"); }); }} />}
      </section>

      {showSubmission && <Modal title="New application" onClose={() => setShowSubmission(false)}>
        <form className="form-stack" onSubmit={submitApplication}>
          <label>Company name<input value={companyName} onChange={(event) => setCompanyName(event.target.value)} required /></label>
          <label>Deck text<textarea value={deckText} onChange={(event) => setDeckText(event.target.value)} rows={12} required /></label>
          <div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setShowSubmission(false)}>Cancel</button><button type="submit" className="command-button" disabled={busy === "submit"}>{busy === "submit" ? <LoaderCircle className="spin" size={17} /> : <FileText size={17} />}Extract claims</button></div>
        </form>
      </Modal>}

      {showThesis && thesis && <Modal title="Fund thesis" onClose={() => setShowThesis(false)}>
        <form className="form-stack" onSubmit={saveThesis}>
          <label>Sectors<input value={thesis.sectors.join(", ")} onChange={(event) => setThesis({ ...thesis, sectors: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
          <label>Stage<input value={thesis.stage} onChange={(event) => setThesis({ ...thesis, stage: event.target.value })} /></label>
          <label>Geographies<input value={thesis.geo.join(", ")} onChange={(event) => setThesis({ ...thesis, geo: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
          <label>Risk appetite<select value={thesis.risk_appetite} onChange={(event) => setThesis({ ...thesis, risk_appetite: event.target.value })}><option>low</option><option>medium</option><option>high</option></select></label>
          <div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setShowThesis(false)}>Cancel</button><button type="submit" className="command-button" disabled={busy === "thesis"}><Check size={17} />Save thesis</button></div>
        </form>
      </Modal>}
    </main>
  );
}

function DashboardView({ founders, metrics, search, setSearch, searchChips, isSearching, onSearch, onClear, onSelect, thesis, onEditThesis, latencies, scanRun }: { founders: Founder[]; metrics: Metrics | null; search: string; setSearch: (value: string) => void; searchChips: string[]; isSearching: boolean; onSearch: (event: FormEvent) => void; onClear: () => void; onSelect: (founder: Founder) => void; thesis: Thesis | null; onEditThesis: () => void; latencies: LatencySample[]; scanRun: ScanRun | null }) {
  return <div className="view-grid dashboard-grid">
    <section className="main-column">
      <div className="metric-strip">
        <Metric label="Sourced" value={metrics?.funnel.sourced ?? "-"} icon={<Database size={17} />} color="teal" />
        <Metric label="Screened" value={metrics?.funnel.screened ?? "-"} icon={<Target size={17} />} color="blue" />
        <Metric label="Diligenced" value={metrics?.funnel.diligenced ?? "-"} icon={<ShieldAlert size={17} />} color="coral" />
        <Metric label="Signal to decision" value={metrics?.signal_to_decision_min ? `${metrics.signal_to_decision_min}m` : "-"} icon={<Flame size={17} />} color="amber" />
      </div>
      <div className="list-surface">
        <div className="surface-head"><div><h2>Founder Memory</h2><p>{scanRun ? scanRun.cached ? "Live source unavailable; reviewed cache retained" : `${scanRun.candidates_found} source-backed candidates reviewed; ${scanRun.new_signals} new signals retained` : `${founders.length} candidates with traceable signals`}</p></div><span className="source-badge"><Database size={14} />{scanRun?.cached ? "cache" : scanRun ? "web" : "memory"}</span></div>
        <form className="query-bar" onSubmit={onSearch}><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="technical founder, AI infra, shipped last 30 days, no prior VC" /><button className="icon-button compact" title="Run query" type="submit" disabled={isSearching}>{isSearching ? <LoaderCircle className="spin" size={17} /> : <ChevronRight size={18} />}</button></form>
        {searchChips.length > 0 && <div className="chip-row">{searchChips.map((chip) => <span className="filter-chip" key={chip}>{chip}</span>)}<button className="text-action" onClick={onClear}>Clear</button></div>}
        <div className="founder-table">
          <div className="table-head"><span>Founder</span><span>Founder Score</span><span>Top signals</span><span /></div>
          {founders.map((founder) => <button className="founder-row" key={founder.founder_id} onClick={() => onSelect(founder)}>
            <span className="founder-cell"><span className={`avatar ${founder.origin}`}>{initials(founder.name)}</span><span><strong>{founder.name}</strong><small><i />{founder.origin} evidence</small></span></span>
            <span className="score-cell"><b>{founder.founder_score}</b><span>+/- {founder.band}</span><Trend value={founder.trend} /></span>
            <span className="signal-cell">{founder.top_signals[0] || "No signal"}</span>
            <ChevronRight size={18} className="row-arrow" />
          </button>)}
          {founders.length === 0 && <div className="empty-row">No source-backed founders match this query.</div>}
        </div>
      </div>
    </section>
    <aside className="side-column">
      <section className="thesis-surface"><div className="surface-head"><div><p className="eyebrow">Active thesis</p><h2>{thesis?.stage ?? "Loading"}</h2></div><button className="icon-button compact" title="Edit fund thesis" onClick={onEditThesis}><PanelRightOpen size={17} /></button></div><div className="thesis-list"><span><Target size={15} />{thesis?.sectors.join(", ")}</span><span><Activity size={15} />{thesis?.geo.join(", ")}</span><span><BadgeCheck size={15} />${(thesis?.check_size || 100000).toLocaleString()} check</span><span><ShieldAlert size={15} />{thesis?.risk_appetite} risk appetite</span></div></section>
      <PerformanceSurface latencies={latencies} />
      <section className="signal-map"><div className="surface-head"><div><p className="eyebrow">Evidence posture</p><h2>Signal diversity</h2></div><Sparkles size={18} /></div><div className="radar"><span className="radar-frame frame-one" /><span className="radar-frame frame-two" /><span className="radar-axis axis-x" /><span className="radar-axis axis-y" /><span className="radar-core"><b>03</b><em>MEM</em></span><i className="node n1">GH</i><i className="node n2">HN</i><i className="node n3">GH</i><i className="node n4">W</i><i className="node n5">S</i></div><div className="legend"><span><i className="dot github" />GitHub</span><span><i className="dot hn" />HN</span><span><i className="dot web" />Public web</span></div></section>
    </aside>
  </div>;
}

function PerformanceSurface({ latencies }: { latencies: LatencySample[] }) {
  const successful = latencies.filter((sample) => sample.ok);
  const sorted = [...successful].sort((left, right) => left.ms - right.ms);
  const p50 = sorted.length ? sorted[Math.floor((sorted.length - 1) * 0.5)].ms : null;
  const last = latencies[0];
  const max = Math.max(...latencies.map((sample) => sample.ms), 1);
  const formatLatency = (ms: number | null) => ms === null ? "--" : ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;

  return <section className="performance-surface">
    <div className="surface-head"><div><p className="eyebrow">Session telemetry</p><h2>Stage latency</h2></div><Clock3 size={18} /></div>
    <div className="latency-readouts"><div><small>Last</small><b>{formatLatency(last?.ms ?? null)}</b><span className={last?.ok === false ? "failed" : ""}>{last?.label ?? "Awaiting"}</span></div><div><small>P50</small><b>{formatLatency(p50)}</b><span>{successful.length} samples</span></div></div>
    <div className="latency-trace" aria-label="Recent stage latency trace">{latencies.length ? latencies.slice(0, 8).reverse().map((sample, index) => <span key={`${sample.label}-${index}`} className={sample.ok ? "" : "failed"} style={{ height: `${Math.max(16, Math.round((sample.ms / max) * 42))}px` }} title={`${sample.label}: ${formatLatency(sample.ms)}`} />) : <i />}</div>
  </section>;
}

function Metric({ label, value, icon, color }: { label: string; value: string | number; icon: ReactNode; color: string }) {
  return <div className="metric"><span className={`metric-icon ${color}`}>{icon}</span><span><small>{label}</small><b>{value}</b></span></div>;
}

function FounderView({ founder, profile, outreach, busy, onActivate, onOpenApplication }: { founder: Founder | null; profile: Profile | null; outreach: string | null; busy: string | null; onActivate: () => void; onOpenApplication: (id: string) => void }) {
  if (!founder || !profile) return <Empty icon={<UserRound size={28} />} title="Select a founder from discovery" />;
  const score = profile.score_history.at(-1);
  return <div className="view-grid profile-grid">
    <section className="profile-main">
      <div className="profile-header"><span className={`avatar large ${profile.profile.origin}`}>{initials(profile.profile.name)}</span><div><p className="eyebrow"><i />{profile.profile.origin} provenance</p><h2>{profile.profile.name}</h2><p>{profile.profile.headline || "Founder profile"}</p><span className="location">{profile.profile.location || "Location not disclosed"}</span></div><button className="command-button profile-action" onClick={onActivate} disabled={busy === "activate"}>{busy === "activate" ? <LoaderCircle className="spin" size={17} /> : <Mail size={17} />}Activate</button></div>
      {outreach && <div className="outreach-draft"><div><p className="eyebrow">Review-only outreach draft</p><p>{outreach}</p></div><Send size={19} /></div>}
      <section className="timeline-surface"><div className="surface-head"><div><h2>Evidence timeline</h2><p>Signals retained in shared Memory</p></div><span className="source-badge"><Database size={14} />{profile.signals.length} signals</span></div><div className="timeline">{profile.signals.map((signal) => <div className="timeline-row" key={signal.signal_id}><span className="timeline-date">{displayDate(signal.ts)}</span><span className={`timeline-marker ${signal.source}`} /><div><p>{signal.text}</p><small><i />{signal.source}{signal.url ? " source" : " evidence"}</small></div></div>)}</div></section>
    </section>
    <aside className="profile-side"><section className="score-panel"><p className="eyebrow">Persistent Founder Score</p><div className="score-orbit"><b>{score?.score ?? founder.founder_score}</b><span>+/- {score?.band ?? founder.band}</span></div><Trend value={founder.trend} /><p>{profile.profile.bio}</p></section><section className="app-links"><div className="surface-head"><h2>Applications</h2><span>{profile.applications.length}</span></div>{profile.applications.length ? profile.applications.map((id) => <button key={id} onClick={() => onOpenApplication(id)}><FileText size={16} />{id.slice(-6)}<ChevronRight size={16} /></button>) : <p>No application yet. Activation creates a review-only outreach draft.</p>}</section></aside>
  </div>;
}

function ApplicationView({ application, nextStage, busy, onRun, onDecide, onNew, latencies }: { application: Application | null; nextStage: "screen" | "diligence" | "memo" | "adversary" | null; busy: string | null; onRun: (stage: "screen" | "diligence" | "memo" | "adversary") => void; onDecide: (action: "approve" | "reject") => void; onNew: () => void; latencies: LatencySample[] }) {
  if (!application) return <Empty icon={<FileText size={28} />} title="Create an application to begin evidence review" action="New application" onAction={onNew} />;
  const runLabel: Record<NonNullable<typeof nextStage>, string> = { screen: "Run 3-axis screen", diligence: "Run truth-gap diligence", memo: "Write investment memo", adversary: "Run Devil's Advocate" };
  return <div className="workbench">
    <div className="workbench-head"><div><p className="eyebrow">{application.status}</p><h2>{application.company_name}</h2><p>{application.claims.length} deck claims, evidence-first workflow</p></div>{nextStage ? <button className="command-button" onClick={() => onRun(nextStage)} disabled={busy === nextStage}>{busy === nextStage ? <LoaderCircle className="spin" size={17} /> : nextStage === "adversary" ? <Bot size={17} /> : <Sparkles size={17} />}{runLabel[nextStage]}</button> : <div className={`decision-status ${application.status}`}>{application.status === "approved" ? <BadgeCheck size={18} /> : application.status === "rejected" ? <X size={18} /> : <ClipboardCheck size={18} />}{application.status}</div>}</div>
    <div className="stage-rail"><StageDot label="Claims" ready /><StageDot label="Screen" ready={Boolean(application.axes)} /><StageDot label="Diligence" ready={Boolean(application.diligence)} /><StageDot label="Memo" ready={Boolean(application.memo)} /><StageDot label="Counter-case" ready={Boolean(application.adversarial)} /></div>
    <PerformanceSurface latencies={latencies} />
    <div className="workbench-grid">
      <section className="claims-panel"><div className="surface-head"><div><h2>Claims</h2><p>Exact deck spans retained</p></div><FileText size={18} /></div>{application.claims.map((claim) => <article className="claim" key={claim.claim_id}><span className={`claim-type ${claim.type}`}>{claim.type}</span><p>{claim.text}</p><small>{claim.source_span ? "Exact deck span" : "Unverifiable without span"}</small></article>)}</section>
      <section className="analysis-panel">
        {!application.axes && <Pending title="Screening is ready" body="Run the independent Founder, Market, and Idea versus Market axes." />}
        {application.axes && <AxesPanel axes={application.axes} />}
        {application.diligence && <DiligencePanel diligence={application.diligence} />}
        {application.memo && <MemoPanel memo={application.memo} />}
        {application.adversarial && application.decision_brief && <AdversaryPanel adversarial={application.adversarial} brief={application.decision_brief} />}
        {application.memo && !nextStage && application.status === "open" && <div className="human-gate"><div><p className="eyebrow">Human gate</p><h3>Commitment stays with the investment committee</h3><p>{application.memo.recommendation.rationale}</p></div><div><button className="reject-button" onClick={() => onDecide("reject")} disabled={busy === "reject"}>Reject</button><button className="approve-button" onClick={() => onDecide("approve")} disabled={busy === "approve"}>{busy === "approve" ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}Approve $100K</button></div></div>}
      </section>
    </div>
  </div>;
}

function AxesPanel({ axes }: { axes: Axes }) { return <section className="analysis-section"><div className="section-title"><Target size={18} /><div><h3>Three independent axes</h3><p>No blended score</p></div></div><div className="axes-grid"><article><small>Founder</small><b>{axes.founder.score}<em>/10</em></b><Trend value={axes.founder.trend as Founder["trend"]} /><p>{axes.founder.rationale}</p></article><article><small>Market</small><b className="word-score">{axes.market.rating}</b><p>{axes.market.rationale}</p></article><article><small>Idea vs. market</small><b className="word-score">{axes.idea_vs_market.verdict}</b><p>{axes.idea_vs_market.rationale}</p></article></div></section>; }

function DiligencePanel({ diligence }: { diligence: NonNullable<Application["diligence"]> }) { return <section className="analysis-section"><div className="section-title"><ShieldAlert size={18} /><div><h3>Truth-gap diligence</h3><p>Claim verdicts resolved against Memory</p></div></div><div className="diligence-list">{diligence.claims.map((claim) => <article key={claim.claim_id}><span className={`verdict ${claim.verdict}`}>{claim.verdict}</span><div><p>{claim.note}</p><small>Trust: {claim.trust} · {claim.evidence.length} evidence records</small></div></article>)}</div>{diligence.gaps.length > 0 && <div className="disclosure-gaps"><Database size={16} /><div><b>Data disclosure</b><span>{diligence.gaps.join(" · ")}</span></div></div>}</section>; }

function MemoPanel({ memo }: { memo: NonNullable<Application["memo"]> }) { return <section className="analysis-section"><div className="section-title"><FileText size={18} /><div><h3>Investment memo</h3><p>{memo.recommendation.invest ? "Evidence-supported recommendation" : "Evidence threshold not met"}</p></div><span className={memo.recommendation.invest ? "recommendation yes" : "recommendation no"}>{memo.recommendation.invest ? "Invest" : "Hold"}</span></div><div className="memo-copy">{Object.entries(memo.sections).map(([key, value]) => <article key={key}><h4>{key.replace("_", " ")}</h4><p>{value}</p></article>)}</div><div className="memo-footer"><span>Based on {memo.recommendation.based_on.length} committed claims</span><b>${memo.recommendation.amount.toLocaleString()}</b></div></section>; }

function AdversaryPanel({ adversarial, brief }: { adversarial: NonNullable<Application["adversarial"]>; brief: NonNullable<Application["decision_brief"]> }) { return <section className="analysis-section adversary-section"><div className="section-title"><Bot size={18} /><div><h3>Devil&apos;s Advocate</h3><p>{adversarial.persona}</p></div></div>{adversarial.objections.map((objection, index) => <article className="objection" key={`${objection.text}-${index}`}><span className={`verification ${objection.verification}`}>{objection.verification}</span><p>{objection.text}</p><small>{objection.label === "speculation" ? "Speculation - no evidence cited" : `${objection.evidence?.length || 0} cited Memory signals`}</small></article>)}<div className="decision-brief"><ClipboardCheck size={17} /><div><b>Decision Brief</b><p>{brief.summary}</p></div></div></section>; }

function DecisionView({ queue, application, onOpen }: { queue: QueueItem[]; application: Application | null; onOpen: (id: string) => void }) { return <div className="decision-layout"><section className="decision-list"><div className="surface-head"><div><h2>Open decisions</h2><p>Memo + verified attacks remain side by side</p></div><span>{queue.length}</span></div>{queue.map((item) => <button className="queue-row" key={item.application_id} onClick={() => onOpen(item.application_id)}><span className="queue-icon"><ClipboardCheck size={18} /></span><span><strong>{item.company}</strong><small>{item.recommendation.invest ? "Invest recommendation" : "Hold recommendation"}</small></span><ChevronRight size={18} /></button>)}{!queue.length && <div className="queue-empty"><BadgeCheck size={23} />No memo-ready decisions are waiting.</div>}</section><section className="audit-panel"><div className="surface-head"><div><h2>Decision packet</h2><p>{application ? application.company_name : "Select a queue item"}</p></div></div>{application?.decision_brief ? <div className="brief-card"><ClipboardCheck size={19} /><p>{application.decision_brief.summary}</p></div> : <Pending title="Human review stays outside the graph" body="A memo-ready application appears here after the bounded stages complete." />}</section></div>; }

function Pending({ title, body }: { title: string; body: string }) { return <div className="pending"><LoaderCircle size={19} /><div><h3>{title}</h3><p>{body}</p></div></div>; }
function Empty({ icon, title, action, onAction }: { icon: ReactNode; title: string; action?: string; onAction?: () => void }) { return <div className="empty"><span>{icon}</span><h2>{title}</h2>{action && <button className="command-button" onClick={onAction}>{action}</button>}</div>; }
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) { return <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="surface-head"><h2>{title}</h2><button className="icon-button compact" title="Close" onClick={onClose}><X size={17} /></button></div>{children}</section></div>; }
