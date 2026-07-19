// Mock founder data for dashboard. Synthetic entries render with dashed
// borders to signal cold-start / low-evidence rows.

export type Origin = "github" | "hn" | "inbound" | "synthetic";
export type Trend = "up" | "flat" | "down";

export type Founder = {
  id: string;
  name: string;
  handle: string;
  origin: Origin;
  score: number;
  band: number;
  trend: Trend;
  top_signals: string[];
  has_open_app: boolean;
  tags: string[]; // used for /api/query matching
};

export const FOUNDERS: Founder[] = [
  {
    id: "f_irisnk",
    name: "Iris Nakamura",
    handle: "@irisnk",
    origin: "github",
    score: 82,
    band: 9,
    trend: "up",
    top_signals: [
      "3 AI-infra repos shipped in last 30d",
      "ex-infra @ Stripe, 4y",
      "no prior VC round",
    ],
    has_open_app: true,
    tags: ["ai infra", "technical", "shipped 12d ago", "no prior vc"],
  },
  {
    id: "f_devon",
    name: "Devon Marsh",
    handle: "devon.marsh",
    origin: "inbound",
    score: 71,
    band: 14,
    trend: "flat",
    top_signals: [
      "Deck cites 4 quantified claims",
      "Solo founder, deep tech",
      "2 GitHub repos, low activity",
    ],
    has_open_app: true,
    tags: ["deep tech", "solo", "inbound deck"],
  },
  {
    id: "f_priya",
    name: "Priya Raman",
    handle: "@praman",
    origin: "hn",
    score: 68,
    band: 11,
    trend: "up",
    top_signals: [
      "Show HN post, 412 upvotes",
      "Open-source LLM eval framework",
      "Prior exit, undisclosed size",
    ],
    has_open_app: false,
    tags: ["ai infra", "open source", "shipped 4d ago", "technical"],
  },
  {
    id: "f_kai",
    name: "Kai Osterberg",
    handle: "@kaios",
    origin: "github",
    score: 64,
    band: 12,
    trend: "flat",
    top_signals: [
      "Rust systems contributor, 6y",
      "No public product yet",
      "Active on niche infra forums",
    ],
    has_open_app: false,
    tags: ["technical", "infra", "no prior vc"],
  },
  {
    id: "f_mira",
    name: "Mira Chen",
    handle: "mira.chen",
    origin: "inbound",
    score: 61,
    band: 15,
    trend: "up",
    top_signals: [
      "B2B SaaS, cited $50K MRR",
      "One flagged claim (contradicted)",
      "Team of 2, both technical",
    ],
    has_open_app: true,
    tags: ["saas", "technical", "revenue-claim"],
  },
  {
    id: "f_ao",
    name: "A. Okonkwo",
    handle: "—",
    origin: "synthetic",
    score: 59,
    band: 22,
    trend: "down",
    top_signals: [
      "No GitHub footprint",
      "Cold-start: low evidence density",
      "Name-only mention in HN thread",
    ],
    has_open_app: false,
    tags: ["cold-start", "synthetic"],
  },
  {
    id: "f_lars",
    name: "Lars Henriksen",
    handle: "@larsh",
    origin: "hn",
    score: 54,
    band: 13,
    trend: "down",
    top_signals: [
      "HN comment history, 3y",
      "No shipped product",
      "Repeated pivot signals",
    ],
    has_open_app: false,
    tags: ["ideation", "no product"],
  },
  {
    id: "f_synth2",
    name: "R. Vasquez",
    handle: "—",
    origin: "synthetic",
    score: 47,
    band: 26,
    trend: "flat",
    top_signals: [
      "Enrichment stub, unverified",
      "Single inbound touch, 3w ago",
      "No corroborating source",
    ],
    has_open_app: false,
    tags: ["cold-start", "synthetic", "unverified"],
  },
];

export function matchQuery(q: string, f: Founder): string[] {
  const terms = q
    .toLowerCase()
    .split(/[,;]| and /)
    .map((t) => t.trim())
    .filter(Boolean);
  if (terms.length === 0) return [];
  const hay = [
    ...f.tags,
    ...f.top_signals.map((s) => s.toLowerCase()),
    f.origin,
  ].join(" | ");
  const hits: string[] = [];
  for (const t of terms) {
    // Very loose contains match — this is a demo endpoint.
    if (hay.includes(t)) hits.push(t);
    else {
      // token-level fallback
      const tokens = t.split(/\s+/).filter((x) => x.length > 2);
      if (tokens.length && tokens.every((tok) => hay.includes(tok))) hits.push(t);
    }
  }
  return hits;
}
