// Application-flow mock data. Drives GET /api/applications/{id},
// /api/decisions/queue, /api/audit, /api/metrics.
// Deterministic, in-repo — no LLM output at request time.

export type ClaimType = "traction" | "team" | "market" | "product";
export type ClaimTrust = "high" | "med" | "low" | "contradicted";
export type ClaimVerdict = "supported" | "contradicted" | "unverifiable";

export type Claim = {
  id: string;
  type: ClaimType;
  text: string;
  /** Slide + verbatim quote from the deck. `null` when extractor found no exact quote. */
  source_span: { location: string; quote: string } | null;
  /** Filled in after Diligence runs. */
  trust: ClaimTrust | null;
  verdict: ClaimVerdict | null;
  /** id of a diligence signal that contradicts / supports the claim */
  linked_signal_id?: string | null;
};

export type AxisVerdict = "pass" | "concern" | "fail";
export type AxisCard = {
  key: "founder" | "market" | "idea_vs_market";
  label: string;
  verdict: AxisVerdict;
  trend: "up" | "flat" | "down";
  headline: string;
  rationale: string;
  factors: string[];
};

export type DiligenceSignal = {
  id: string;
  source: string;
  quote: string;
  supports?: string[];
  contradicts?: string[];
};

export type DiligenceGap = {
  id: string;
  label: string;
  note?: string;
};

export type Memo = {
  snapshot: string;
  hypotheses: string[];
  swot: { strengths: string[]; weaknesses: string[]; opportunities: string[]; threats: string[] };
  problem_product: string;
  traction_kpis: string;
  recommendation: {
    verdict: "invest" | "pass" | "revisit";
    amount_usd: number | null;
    rationale: string;
    based_on: string[];
  };
};

export type ObjectionSeverity = "red" | "yellow" | "dim";
export type ObjectionLabel = "evidence-backed" | "speculation";
export type ObjectionStatus = "verified" | "unverified" | "n/a";

export type Objection = {
  id: string;
  persona: string; // e.g. "Founder-Risk Partner"
  objection: string;
  label: ObjectionLabel;
  status: ObjectionStatus;
  severity: ObjectionSeverity;
  claim_id?: string;
};

export type DecisionBrief = {
  red: number;
  yellow: number;
  dim: number;
  contested_pairs: Array<{
    id: string;
    severity: ObjectionSeverity;
    claim_id?: string;
    objection_id: string;
    label: string; // short summary of the pair
  }>;
  /** Rendered verbatim in the UI. */
  summary: string;
};

export type Adversary = {
  bull_case: string;
  bear_case: string;
  kill_criteria: string[];
  objections: Objection[];
  decision_brief: DecisionBrief;
};

export type StageState = "not_run" | "complete";
export type DecisionState = "pending" | "approved" | "rejected" | null;

export type AuditEvent = {
  at: string; // ISO
  stage:
    | "sourced"
    | "activated"
    | "deck_uploaded"
    | "claims_extracted"
    | "screened"
    | "diligence"
    | "memo"
    | "adversary"
    | "decision";
  actor: "agent" | "human";
  note: string;
};

export type Application = {
  id: string;
  company: string;
  founder_id: string;
  founder_name: string;
  submitted_at: string;
  deck_pages: number;
  stage: {
    claims: StageState;
    screen: StageState;
    diligence: StageState;
    memo: StageState;
    adversary: StageState;
  };
  claims: Claim[];
  screen: AxisCard[] | null;
  diligence: {
    signals: DiligenceSignal[];
    gaps: DiligenceGap[];
  } | null;
  memo: Memo | null;
  adversary: Adversary | null;
  decision: DecisionState;
  audit: AuditEvent[];
};

function iso(daysAgo: number, hour = 9, minute = 0): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

// ─────────────────────────────────────────────────────────────────────────────
// app_iris_1 — Deterministic Labs. Fully processed. In the decision queue.
// ─────────────────────────────────────────────────────────────────────────────
const irisApp: Application = {
  id: "app_iris_1",
  company: "Deterministic Labs",
  founder_id: "f_irisnk",
  founder_name: "Iris Nakamura",
  submitted_at: iso(34),
  deck_pages: 12,
  stage: {
    claims: "complete",
    screen: "complete",
    diligence: "complete",
    memo: "complete",
    adversary: "complete",
  },
  claims: [
    {
      id: "c_iris_1",
      type: "product",
      text: "Deterministic re-runs of LLM eval suites (bit-identical output across runs).",
      source_span: {
        location: "slide 3",
        quote:
          "eval-deterministic guarantees bit-identical output across N re-runs of the same eval suite, given the same model + seed.",
      },
      trust: "high",
      verdict: "supported",
      linked_signal_id: "ds_iris_1",
    },
    {
      id: "c_iris_2",
      type: "traction",
      text: "412 GitHub stars on eval-deterministic; +180 in the last 48 hours.",
      source_span: {
        location: "slide 6",
        quote: "412 stars, 60+ contributors, ~180 stars added in the 48h after Show HN.",
      },
      trust: "high",
      verdict: "supported",
      linked_signal_id: "ds_iris_2",
    },
    {
      id: "c_iris_3",
      type: "team",
      text: "Founder led payments-reliability infra at Stripe for 4 years.",
      source_span: {
        location: "slide 9",
        quote: "4 years at Stripe on the payments-reliability infra team.",
      },
      trust: "high",
      verdict: "supported",
      linked_signal_id: "ds_iris_3",
    },
    {
      id: "c_iris_4",
      type: "market",
      text: "LLM eval tooling is a $1.4B market by 2027.",
      source_span: null,
      trust: "med",
      verdict: "unverifiable",
      linked_signal_id: null,
    },
    {
      id: "c_iris_5",
      type: "traction",
      text: "3 design partners already integrating v0.3 into internal CI.",
      source_span: {
        location: "slide 7",
        quote: "3 design partners integrating v0.3 into CI (LOIs, not paid).",
      },
      trust: "med",
      verdict: "unverifiable",
      linked_signal_id: null,
    },
  ],
  screen: [
    {
      key: "founder",
      label: "Founder",
      verdict: "pass",
      trend: "up",
      headline: "Strong technical operator, on-thesis background.",
      rationale:
        "4y payments-reliability infra at Stripe. Public shipping cadence (34 commits / 7d) matches self-described focus. No prior VC round — no reset cost.",
      factors: [
        "shipping cadence · verified",
        "on-thesis background · verified",
        "public writing on determinism · verified",
      ],
    },
    {
      key: "market",
      label: "Market",
      verdict: "concern",
      trend: "flat",
      headline: "Real pain, but sizing claim not verifiable.",
      rationale:
        "The reproducibility pain in LLM eval is well-documented in developer forums. The $1.4B TAM number in the deck has no source and does not reconcile against public analyst reports.",
      factors: [
        "pain: strong dev-forum evidence",
        "TAM cite: unverifiable",
        "adjacent tools: growing category",
      ],
    },
    {
      key: "idea_vs_market",
      label: "Idea vs Market",
      verdict: "pass",
      trend: "up",
      headline: "Wedge is narrow and defensible.",
      rationale:
        "Determinism as a primitive is under-served vs. broader eval frameworks. Design-partner integrations suggest sequencing (infra → eval → benchmarks) is right.",
      factors: [
        "wedge specificity: narrow ✓",
        "sequencing: infra-first ✓",
        "moat: seeded via OSS trust",
      ],
    },
  ],
  diligence: {
    signals: [
      {
        id: "ds_iris_1",
        source: "github.com/irisnk/eval-deterministic · v0.3 release notes",
        quote:
          "Guarantees bit-identical output across re-runs when the (model, seed, prompt, tool-config) tuple is held constant.",
        supports: ["c_iris_1"],
      },
      {
        id: "ds_iris_2",
        source: "github · stars API · sampled 2025-07-16",
        quote: "412 stars; delta +180 in the trailing 48h following the HN Show post.",
        supports: ["c_iris_2"],
      },
      {
        id: "ds_iris_3",
        source: "linkedin · public work history",
        quote: "Iris Nakamura — Stripe — Payments Reliability Infra — Mar 2020 → Feb 2024.",
        supports: ["c_iris_3"],
      },
    ],
    gaps: [
      { id: "g_iris_1", label: "Cap table: not disclosed" },
      {
        id: "g_iris_2",
        label: "Design-partner names: withheld",
        note: "Iris cited 3 partners on slide 7 — no names, no LOIs attached to deck.",
      },
      { id: "g_iris_3", label: "Revenue: pre-revenue (confirmed, not a gap)" },
    ],
  },
  memo: {
    snapshot:
      "Solo technical founder, ex-Stripe infra, shipping open-source determinism primitives for LLM evals. 412 GitHub stars, three design partners on v0.3, pre-revenue. Raising a first check.",
    hypotheses: [
      "Determinism is a wedge into a broader eval-infra category (bench → guardrails → CI).",
      "OSS distribution seeds trust that a closed product cannot replicate in <18 months.",
      "The founder is closer to a systems-infra founder than an ML-research founder — this is a plus for the category.",
    ],
    swot: {
      strengths: [
        "Founder's Stripe pedigree in payments-reliability transfers directly.",
        "OSS traction is real and recent.",
      ],
      weaknesses: [
        "No paid design partners yet; LOIs only.",
        "Sizing claim in deck is unverifiable.",
      ],
      opportunities: [
        "First-mover on eval-determinism as a category.",
        "Adjacent expansion into eval-CI and guardrail evaluation.",
      ],
      threats: [
        "OSS eval frameworks may absorb the feature.",
        "Foundation-model providers releasing their own determinism guarantees.",
      ],
    },
    problem_product:
      "LLM eval suites drift across runs even with fixed seeds because tool-call ordering, retry timing, and non-deterministic tokenization leak into results. eval-deterministic fixes this by pinning the full (model, seed, prompt, tool-config) tuple and re-executing under a controlled scheduler. The output is bit-identical, which unlocks trustworthy CI.",
    traction_kpis:
      "412 stars, +180 in 48h post-launch. 60+ contributors. 3 design partners actively integrating (unpaid). No revenue. Repo age: 58 days.",
    recommendation: {
      verdict: "invest",
      amount_usd: 500000,
      rationale:
        "Founder background + narrow wedge + verifiable OSS traction cover the founder and idea-vs-market axes. Market axis is a concern only in sizing, not in pain — this is acceptable at pre-seed. Recommend a $500k first check.",
      based_on: ["c_iris_1", "c_iris_2", "c_iris_3", "c_iris_5"],
    },
  },
  adversary: {
    bull_case:
      "eval-deterministic becomes the reference implementation for reproducible LLM evals; foundation-model vendors integrate against it. Category-defining wedge; the OSS trust flywheel makes a closed competitor structurally later.",
    bear_case:
      "Determinism is a feature, not a company. LangSmith / Braintrust / OSS forks ship equivalent behavior within 12 months and the wedge collapses into a checkbox. Founder is an infra IC, not a category-defining CEO.",
    kill_criteria: [
      "No paid design partner converted within 6 months of first check.",
      "A major eval framework (LangSmith, Braintrust, or OSS equivalent) ships equivalent determinism as a default in the next 2 quarters.",
      "Founder cannot articulate the eval-CI product surface at the 3-month check-in.",
    ],
    objections: [
      {
        id: "obj_iris_1",
        persona: "Founder-Risk Partner",
        objection:
          "Solo technical founder with no prior CEO experience. Category-defining products typically require a commercial co-founder in the first 12 months; there is no plan for one in the deck.",
        label: "evidence-backed",
        status: "unverified",
        severity: "yellow",
        claim_id: "c_iris_3",
      },
      {
        id: "obj_iris_2",
        persona: "Market-Structure Partner",
        objection:
          "The $1.4B TAM figure on slide 4 does not reconcile against any public analyst report. Treat this as speculation until the founder sources it in-person.",
        label: "speculation",
        status: "unverified",
        severity: "red",
        claim_id: "c_iris_4",
      },
      {
        id: "obj_iris_3",
        persona: "Competitive-Landscape Partner",
        objection:
          "LangSmith / Braintrust ship monthly. The wedge could collapse to a checkbox feature; no evidence the founder has a moat plan beyond OSS trust.",
        label: "speculation",
        status: "n/a",
        severity: "dim",
      },
      {
        id: "obj_iris_4",
        persona: "Traction-Quality Partner",
        objection:
          "3 design partners are cited but names are withheld and none are paid. OSS stars are real, but paid conversion is the leading indicator we care about.",
        label: "evidence-backed",
        status: "verified",
        severity: "yellow",
        claim_id: "c_iris_5",
      },
    ],
    decision_brief: {
      red: 1,
      yellow: 2,
      dim: 1,
      contested_pairs: [
        {
          id: "pair_iris_1",
          severity: "red",
          claim_id: "c_iris_4",
          objection_id: "obj_iris_2",
          label: "TAM cite vs. no public analyst source",
        },
        {
          id: "pair_iris_2",
          severity: "yellow",
          claim_id: "c_iris_3",
          objection_id: "obj_iris_1",
          label: "Solo-founder pedigree vs. missing commercial co-founder plan",
        },
        {
          id: "pair_iris_3",
          severity: "yellow",
          claim_id: "c_iris_5",
          objection_id: "obj_iris_4",
          label: "3 design partners vs. no paid conversion, names withheld",
        },
        {
          id: "pair_iris_4",
          severity: "dim",
          objection_id: "obj_iris_3",
          label: "Moat plan vs. adjacent eval-frameworks release cadence",
        },
      ],
      summary:
        "Decision Brief: 1 red, 2 yellow, 1 dim contested pairs; human review required.",
    },
  },
  decision: "pending",
  audit: [
    { at: iso(58, 8, 12), stage: "sourced", actor: "agent", note: "Founder f_irisnk enters cache via github origin (first repo commit)." },
    { at: iso(41, 10, 3), stage: "activated", actor: "human", note: "Analyst clicks Activate; outreach draft rendered." },
    { at: iso(34, 14, 47), stage: "deck_uploaded", actor: "human", note: "Deck received via warm intro (12 slides)." },
    { at: iso(34, 14, 49), stage: "claims_extracted", actor: "agent", note: "5 claims extracted; 4 with source_span, 1 null." },
    { at: iso(33, 9, 2), stage: "screened", actor: "agent", note: "3-axis screen complete: founder=pass, market=concern, idea_vs_market=pass." },
    { at: iso(30, 11, 30), stage: "diligence", actor: "agent", note: "Diligence: 3 supporting signals, 3 open gaps documented." },
    { at: iso(7, 15, 22), stage: "memo", actor: "agent", note: "Memo drafted; recommendation=invest, $500,000 first check." },
    { at: iso(1, 9, 15), stage: "adversary", actor: "agent", note: "Devil's Advocate pass: 4 objections across 4 personas; brief = 1 red, 2 yellow, 1 dim." },
  ],
};

// ─────────────────────────────────────────────────────────────────────────────
// app_mira_1 — Chen & Co. Memo drafted, adversary not run yet.
// ─────────────────────────────────────────────────────────────────────────────
const miraApp: Application = {
  id: "app_mira_1",
  company: "Chen & Co",
  founder_id: "f_mira",
  founder_name: "Mira Chen",
  submitted_at: iso(3),
  deck_pages: 14,
  stage: {
    claims: "complete",
    screen: "complete",
    diligence: "complete",
    memo: "complete",
    adversary: "not_run",
  },
  claims: [
    {
      id: "c_mira_1",
      type: "traction",
      text: "$50,000 MRR at 6 weeks post-launch.",
      source_span: {
        location: "slide 5",
        quote: "$50K MRR reached in week 6 post-launch (chart, y-axis in USD).",
      },
      trust: "contradicted",
      verdict: "contradicted",
      linked_signal_id: "ds_mira_1",
    },
    {
      id: "c_mira_2",
      type: "team",
      text: "Two co-founders, both technical.",
      source_span: {
        location: "slide 10",
        quote: "Mira Chen (CEO, ex-Datadog) and Alex Park (CTO, ex-Segment).",
      },
      trust: "high",
      verdict: "supported",
      linked_signal_id: null,
    },
    {
      id: "c_mira_3",
      type: "product",
      text: "AI-native billing reconciliation for mid-market B2B SaaS.",
      source_span: {
        location: "slide 2",
        quote:
          "Chen & Co reconciles Stripe / Chargebee / NetSuite for mid-market SaaS with an AI agent.",
      },
      trust: "med",
      verdict: "unverifiable",
      linked_signal_id: null,
    },
    {
      id: "c_mira_4",
      type: "market",
      text: "40% of mid-market SaaS finance teams still reconcile billing manually.",
      source_span: null,
      trust: "low",
      verdict: "unverifiable",
      linked_signal_id: null,
    },
  ],
  screen: [
    {
      key: "founder",
      label: "Founder",
      verdict: "pass",
      trend: "up",
      headline: "Two technical co-founders, category-adjacent background.",
      rationale:
        "Both founders shipped billing- and observability-adjacent products before. No prior venture round. Complementary skills.",
      factors: [
        "ex-Datadog / ex-Segment · verified",
        "shipped billing product before · verified",
        "no prior VC · verified",
      ],
    },
    {
      key: "market",
      label: "Market",
      verdict: "concern",
      trend: "flat",
      headline: "Real pain, sizing claim unverified.",
      rationale:
        "Reconciliation pain in mid-market SaaS is well-documented and there is willingness-to-pay evidence. The 40%-manual claim in the deck has no cited source.",
      factors: [
        "pain: verifiable via case studies",
        "40% claim: unverifiable",
        "adjacent products: growing spend",
      ],
    },
    {
      key: "idea_vs_market",
      label: "Idea vs Market",
      verdict: "fail",
      trend: "down",
      headline: "Revenue timing does not reconcile with public statements.",
      rationale:
        "Deck cites $50K MRR at 6 weeks. A public HN comment from the same founder 21 days earlier described the product as 'pre-revenue, waitlist only, targeting Q3 launch'. This must be resolved in a live conversation before advancing.",
      factors: [
        "traction claim contradicted",
        "sequencing unclear",
        "requires founder conversation",
      ],
    },
  ],
  diligence: {
    signals: [
      {
        id: "ds_mira_1",
        source: "news.ycombinator.com · comment by mira_c · 21d before deck submission",
        quote:
          "We're pre-revenue, waitlist-only right now. Targeting Q3 launch — happy to chat then.",
        contradicts: ["c_mira_1"],
      },
    ],
    gaps: [
      { id: "g_mira_1", label: "Cap table: not disclosed" },
      { id: "g_mira_2", label: "Customer list: 'names withheld pending call'" },
      {
        id: "g_mira_3",
        label: "MRR reconciliation: no exported Stripe report attached",
        note: "Requested in follow-up; not received at time of screening.",
      },
    ],
  },
  memo: {
    snapshot:
      "Two technical co-founders (ex-Datadog / ex-Segment) building AI-native billing reconciliation for mid-market SaaS. Deck cites $50K MRR at 6 weeks; a public HN comment from the same founder 21 days earlier describes the product as pre-revenue and waitlist-only. Requires founder conversation before decision.",
    hypotheses: [
      "Reconciliation is a real, willingness-to-pay pain in mid-market SaaS.",
      "The revenue timing inconsistency is a sequencing error, not fabrication — resolvable in a call.",
      "Two technical founders can ship the product, but a commercial hire will be needed for enterprise-grade sales.",
    ],
    swot: {
      strengths: [
        "Category-adjacent founder backgrounds.",
        "Real willingness-to-pay evidence in adjacent products.",
      ],
      weaknesses: [
        "One deck claim publicly contradicted.",
        "No exported customer list or Stripe report shared.",
      ],
      opportunities: [
        "Mid-market SaaS reconciliation spend is growing.",
        "AI-native workflow could win category if trust is established.",
      ],
      threats: [
        "Trust erosion from unresolved traction claim.",
        "Incumbents (Chargebee, Maxio) shipping AI features.",
      ],
    },
    problem_product:
      "Mid-market SaaS finance teams reconcile Stripe, Chargebee, and NetSuite manually. Chen & Co runs an AI agent that maps and closes discrepancies weekly.",
    traction_kpis:
      "Deck cites $50K MRR at week 6; contradicted by founder's own public statement from 21d earlier. Two technical founders full-time; no external hires. No cap table shared.",
    recommendation: {
      verdict: "revisit",
      amount_usd: null,
      rationale:
        "Do not advance until the revenue-timing inconsistency is resolved in a live conversation. Pain is real; team is credible; a single contradiction should not tank the process but must be reconciled before a check.",
      based_on: ["c_mira_1", "c_mira_2", "c_mira_3"],
    },
  },
  adversary: null,
  decision: null,
  audit: [
    { at: iso(24, 11, 4), stage: "sourced", actor: "agent", note: "Founder f_mira enters cache via inbound origin." },
    { at: iso(3, 9, 0), stage: "deck_uploaded", actor: "human", note: "Deck submitted via founders form (14 slides)." },
    { at: iso(3, 9, 2), stage: "claims_extracted", actor: "agent", note: "4 claims extracted; 1 contradicted against a 21d-old public post." },
    { at: iso(3, 10, 15), stage: "screened", actor: "agent", note: "3-axis screen complete: founder=pass, market=concern, idea_vs_market=fail." },
    { at: iso(2, 14, 22), stage: "diligence", actor: "agent", note: "Diligence: 1 contradicting signal, 3 open gaps." },
    { at: iso(1, 16, 40), stage: "memo", actor: "agent", note: "Memo drafted; recommendation=revisit, no amount." },
  ],
};

// ─────────────────────────────────────────────────────────────────────────────
// app_devon_1 — Marsh Systems. Claims only.
// ─────────────────────────────────────────────────────────────────────────────
const devonApp: Application = {
  id: "app_devon_1",
  company: "Marsh Systems",
  founder_id: "f_devon",
  founder_name: "Devon Marsh",
  submitted_at: iso(4),
  deck_pages: 18,
  stage: {
    claims: "complete",
    screen: "not_run",
    diligence: "not_run",
    memo: "not_run",
    adversary: "not_run",
  },
  claims: [
    {
      id: "c_devon_1",
      type: "product",
      text: "CV pipeline detects logistics anomalies at 94% precision on internal benchmark.",
      source_span: {
        location: "slide 6",
        quote:
          "Marsh CV pipeline: 94.2% precision, 88.1% recall on the internal defense-logistics benchmark (n=2,140 frames).",
      },
      trust: null,
      verdict: null,
    },
    {
      id: "c_devon_2",
      type: "team",
      text: "Solo founder, 6 years of CV research at a defense contractor.",
      source_span: {
        location: "slide 9",
        quote: "6y CV research, defense contractor (name under NDA).",
      },
      trust: null,
      verdict: null,
    },
    {
      id: "c_devon_3",
      type: "traction",
      text: "One LOI signed with a Tier-1 defense integrator.",
      source_span: null,
      trust: null,
      verdict: null,
    },
    {
      id: "c_devon_4",
      type: "market",
      text: "Defense logistics AI is a $3.2B addressable market by 2028.",
      source_span: {
        location: "slide 4",
        quote: "$3.2B TAM by 2028 (source: internal estimate).",
      },
      trust: null,
      verdict: null,
    },
  ],
  screen: null,
  diligence: null,
  memo: null,
  adversary: null,
  decision: null,
  audit: [
    { at: iso(11, 8, 20), stage: "sourced", actor: "agent", note: "Founder f_devon enters cache via inbound origin." },
    { at: iso(4, 10, 12), stage: "deck_uploaded", actor: "human", note: "Deck submitted via founders form (18 slides)." },
    { at: iso(4, 10, 14), stage: "claims_extracted", actor: "agent", note: "4 claims extracted; 1 with null source_span." },
  ],
};

export const APPLICATIONS: Record<string, Application> = {
  app_iris_1: irisApp,
  app_mira_1: miraApp,
  app_devon_1: devonApp,
};

// ─────────────────────────────────────────────────────────────────────────────
// Queue helpers (in-memory mutation for demo — server-only calls)
// ─────────────────────────────────────────────────────────────────────────────

export type QueueItem = {
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

export function listQueue(): QueueItem[] {
  return Object.values(APPLICATIONS)
    .filter((a) => a.memo && a.decision !== "approved" && a.decision !== "rejected")
    .map((a) => ({
      id: a.id,
      company: a.company,
      founder_name: a.founder_name,
      founder_id: a.founder_id,
      submitted_at: a.submitted_at,
      recommendation: {
        verdict: a.memo!.recommendation.verdict,
        amount_usd: a.memo!.recommendation.amount_usd,
        one_liner: firstSentence(a.memo!.recommendation.rationale),
      },
      brief: a.adversary?.decision_brief ?? null,
      decision: a.decision,
    }));
}

function firstSentence(s: string): string {
  const i = s.indexOf(". ");
  return i > 0 ? s.slice(0, i + 1) : s;
}

export function listApplications(): Array<
  Pick<Application, "id" | "company" | "founder_name" | "founder_id" | "submitted_at"> & {
    progress: number;
  }
> {
  return Object.values(APPLICATIONS).map((a) => ({
    id: a.id,
    company: a.company,
    founder_name: a.founder_name,
    founder_id: a.founder_id,
    submitted_at: a.submitted_at,
    progress: Object.values(a.stage).filter((s) => s === "complete").length,
  }));
}

// ─────────────────────────────────────────────────────────────────────────────
// Aggregate metrics + audit
// ─────────────────────────────────────────────────────────────────────────────

export function computeMetrics() {
  const apps = Object.values(APPLICATIONS);
  const sourced = 8; // matches FOUNDERS.length in dashboard-data
  const screened = apps.filter((a) => a.stage.screen === "complete").length;
  const diligenced = apps.filter((a) => a.stage.diligence === "complete").length;
  const decided = apps.filter(
    (a) => a.decision === "approved" || a.decision === "rejected",
  ).length;
  return {
    signal_to_decision_min: 214, // deterministic mock — median across processed apps
    funnel: { sourced, screened, diligenced, decided },
  };
}

export function listAudit(applicationId?: string) {
  if (applicationId) {
    const a = APPLICATIONS[applicationId];
    if (!a) return [];
    return a.audit.map((e) => ({ ...e, application_id: a.id, company: a.company }));
  }
  return Object.values(APPLICATIONS)
    .flatMap((a) => a.audit.map((e) => ({ ...e, application_id: a.id, company: a.company })))
    .sort((x, y) => y.at.localeCompare(x.at));
}

// ─────────────────────────────────────────────────────────────────────────────
// Mutations (in-memory, deterministic replay-ready)
// ─────────────────────────────────────────────────────────────────────────────

export function decide(applicationId: string, verdict: "approved" | "rejected", note?: string) {
  const a = APPLICATIONS[applicationId];
  if (!a) return null;
  a.decision = verdict;
  a.audit.push({
    at: new Date().toISOString(),
    stage: "decision",
    actor: "human",
    note:
      (verdict === "approved" ? "Approved" : "Rejected") +
      (note ? ` — ${note}` : ` — human gate; ${a.adversary?.decision_brief.summary ?? "no brief."}`),
  });
  return a;
}

/** Deterministic adversarial pass for the fixture app that has memo but no adversary. */
export function runAdversary(applicationId: string): Application | null {
  const a = APPLICATIONS[applicationId];
  if (!a || !a.memo) return null;
  if (a.adversary) return a;

  if (a.id === "app_mira_1") {
    a.adversary = {
      bull_case:
        "Reconciliation is a real, willingness-to-pay pain and the founders have category-adjacent execution history. If the revenue-timing gap resolves cleanly in-person, this is a check.",
      bear_case:
        "One contradiction on traction is enough at pre-seed. Incumbents (Chargebee, Maxio) are shipping AI features monthly; trust must be established before capital moves.",
      kill_criteria: [
        "Founder cannot produce an exported Stripe / Chargebee report at the follow-up call.",
        "Cap table is more encumbered than the deck implied.",
        "Product surface expands beyond reconciliation before the current wedge is proven.",
      ],
      objections: [
        {
          id: "obj_mira_1",
          persona: "Founder-Risk Partner",
          objection:
            "A public HN comment 21 days before submission described the product as pre-revenue, waitlist-only. The deck cites $50K MRR at week 6. This must be reconciled in a live conversation before capital moves.",
          label: "evidence-backed",
          status: "verified",
          severity: "red",
          claim_id: "c_mira_1",
        },
        {
          id: "obj_mira_2",
          persona: "Market-Structure Partner",
          objection:
            "The '40% still reconcile manually' figure on slide 4 has no citation. Adjacent products (Chargebee, Maxio) publish opposing figures.",
          label: "speculation",
          status: "unverified",
          severity: "yellow",
          claim_id: "c_mira_4",
        },
        {
          id: "obj_mira_3",
          persona: "Competitive-Landscape Partner",
          objection:
            "Chargebee's AI-billing beta is public and Maxio has an announced roadmap. Wedge specificity is not yet demonstrated in the deck.",
          label: "evidence-backed",
          status: "verified",
          severity: "yellow",
        },
        {
          id: "obj_mira_4",
          persona: "Traction-Quality Partner",
          objection:
            "No exported Stripe report attached. Even if MRR is real, the artifact was requested and not received — treat as unverified until it is.",
          label: "evidence-backed",
          status: "unverified",
          severity: "dim",
          claim_id: "c_mira_1",
        },
      ],
      decision_brief: {
        red: 1,
        yellow: 2,
        dim: 1,
        contested_pairs: [
          {
            id: "pair_mira_1",
            severity: "red",
            claim_id: "c_mira_1",
            objection_id: "obj_mira_1",
            label: "$50K MRR week-6 vs. own public 'pre-revenue' post 21d earlier",
          },
          {
            id: "pair_mira_2",
            severity: "yellow",
            claim_id: "c_mira_4",
            objection_id: "obj_mira_2",
            label: "40% manual-recon claim vs. opposing incumbent figures",
          },
          {
            id: "pair_mira_3",
            severity: "yellow",
            objection_id: "obj_mira_3",
            label: "Wedge specificity vs. announced incumbent AI features",
          },
          {
            id: "pair_mira_4",
            severity: "dim",
            claim_id: "c_mira_1",
            objection_id: "obj_mira_4",
            label: "MRR claim vs. missing Stripe export",
          },
        ],
        summary:
          "Decision Brief: 1 red, 2 yellow, 1 dim contested pairs; human review required.",
      },
    };
    a.stage.adversary = "complete";
    a.audit.push({
      at: new Date().toISOString(),
      stage: "adversary",
      actor: "agent",
      note: "Devil's Advocate pass: 4 objections; brief = 1 red, 2 yellow, 1 dim.",
    });
    return a;
  }

  // Generic fallback — should not fire for the demo fixtures.
  a.adversary = {
    bull_case: "Generated on demand — no persona overrides for this application.",
    bear_case: "Generated on demand — no persona overrides for this application.",
    kill_criteria: [],
    objections: [],
    decision_brief: {
      red: 0,
      yellow: 0,
      dim: 0,
      contested_pairs: [],
      summary: "Decision Brief: 0 red, 0 yellow, 0 dim contested pairs; human review required.",
    },
  };
  a.stage.adversary = "complete";
  return a;
}
