// Founder profile detail data. Keyed by founder id; drives /api/founders/[id].
// Deterministic mock — no LLM output — kept in-repo so demos are reproducible.

import type { Origin } from "./dashboard-data";

export type SignalKind = "commit" | "post" | "mention" | "deck" | "release";

export type Signal = {
  id: string;
  kind: SignalKind;
  source: Origin;
  at: string; // ISO
  text: string;
  url?: string;
};

export type Application = {
  id: string;
  company: string;
  status: "screening" | "diligence" | "memo" | "decision" | "declined";
  submitted_at: string; // ISO
};

export type FounderProfile = {
  id: string;
  headline: string;
  location: string;
  bio: string;
  score_history: Array<{ at: string; score: number }>;
  signals: Signal[];
  applications: Application[];
  outreach_draft: string; // returned by /activate
};

// score_history spans ~90 days back, monthly-ish samples, deterministic.
function history(points: number[]): Array<{ at: string; score: number }> {
  const now = Date.now();
  const step = 12 * 24 * 3600 * 1000; // 12 days
  return points.map((s, i) => ({
    at: new Date(now - (points.length - 1 - i) * step).toISOString(),
    score: s,
  }));
}

function iso(daysAgo: number, hour = 9): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

export const PROFILES: Record<string, FounderProfile> = {
  f_irisnk: {
    id: "f_irisnk",
    headline: "Building deterministic LLM eval infra. Ex-Stripe.",
    location: "San Francisco, CA",
    bio: "4y infra at Stripe (payments reliability). Currently shipping open-source tooling for LLM eval determinism. No prior VC round.",
    score_history: history([63, 65, 68, 71, 74, 78, 80, 82]),
    signals: [
      {
        id: "s1",
        kind: "release",
        source: "github",
        at: iso(2),
        text: "Released v0.3 of eval-deterministic — 412 stars, +180 in 48h.",
      },
      {
        id: "s2",
        kind: "commit",
        source: "github",
        at: iso(5),
        text: "34 commits across 3 AI-infra repos in the last 7 days.",
      },
      {
        id: "s3",
        kind: "post",
        source: "hn",
        at: iso(9),
        text: "Show HN: 'A deterministic eval harness for LLM pipelines' — 287 points.",
      },
      {
        id: "s4",
        kind: "mention",
        source: "hn",
        at: iso(21),
        text: "Cited in a top comment on 'the reproducibility crisis in LLM benchmarks'.",
      },
      {
        id: "s5",
        kind: "deck",
        source: "inbound",
        at: iso(34),
        text: "Inbound deck received via warm intro — 12 slides, 4 quantified claims extracted.",
      },
      {
        id: "s6",
        kind: "commit",
        source: "github",
        at: iso(58),
        text: "First public commit on eval-deterministic (repo created).",
      },
    ],
    applications: [
      {
        id: "app_iris_1",
        company: "Deterministic Labs",
        status: "diligence",
        submitted_at: iso(34),
      },
    ],
    outreach_draft:
      "Hi Iris — I've been following eval-deterministic since the Show HN post; the determinism guarantees you're claiming are the exact primitive we think is missing from the current eval stack. We invest at pre-seed in technical founders shipping infra like this. Would you be open to a 30-min call next week? — MG",
  },
  f_devon: {
    id: "f_devon",
    headline: "Solo founder, deep-tech CV pipelines for defense logistics.",
    location: "Austin, TX",
    bio: "Solo technical founder. Prior: 6y CV research at a defense contractor. Deck cites 4 quantified claims, one flagged for verification.",
    score_history: history([70, 71, 72, 71, 72, 71, 71, 71]),
    signals: [
      {
        id: "s1",
        kind: "deck",
        source: "inbound",
        at: iso(4),
        text: "Deck submitted via founders form. Extractor found 4 claims, 1 with contradicted trust.",
      },
      {
        id: "s2",
        kind: "commit",
        source: "github",
        at: iso(11),
        text: "Two private-mirror repos identified; low public activity.",
      },
      {
        id: "s3",
        kind: "mention",
        source: "hn",
        at: iso(40),
        text: "Comment thread on defense-adjacent CV benchmarks.",
      },
    ],
    applications: [
      {
        id: "app_devon_1",
        company: "Marsh Systems",
        status: "screening",
        submitted_at: iso(4),
      },
    ],
    outreach_draft:
      "Hi Devon — thanks for the Marsh Systems deck. Before we take next steps, we'd like to walk through the four quantified claims in slide 6 with you — one currently doesn't reconcile against public sources and we'd rather resolve that in a call than in email. Available this week? — MG",
  },
  f_priya: {
    id: "f_priya",
    headline: "Open-source LLM eval framework maintainer. Prior exit.",
    location: "Bangalore, IN",
    bio: "Prior exit (undisclosed). Currently maintains a widely-used OSS eval framework. Not yet raising publicly.",
    score_history: history([55, 58, 60, 62, 64, 66, 67, 68]),
    signals: [
      {
        id: "s1",
        kind: "release",
        source: "github",
        at: iso(4),
        text: "Cut v1.0 of osseval — release notes cite 60+ contributors.",
      },
      {
        id: "s2",
        kind: "post",
        source: "hn",
        at: iso(12),
        text: "Show HN thread reached 412 upvotes, front page 6h.",
      },
      {
        id: "s3",
        kind: "mention",
        source: "hn",
        at: iso(45),
        text: "Referenced in a broader thread on eval reproducibility.",
      },
    ],
    applications: [],
    outreach_draft:
      "Hi Priya — big fan of osseval, and congrats on v1.0. If you're thinking about turning the framework into a company (or already are), we'd love to meet before you start a formal process. — MG",
  },
  f_kai: {
    id: "f_kai",
    headline: "Rust systems contributor. No public product yet.",
    location: "Stockholm, SE",
    bio: "6y of Rust systems contributions across several infra projects. Active on niche forums; no shipped product to date.",
    score_history: history([60, 61, 63, 64, 64, 64, 64, 64]),
    signals: [
      {
        id: "s1",
        kind: "commit",
        source: "github",
        at: iso(6),
        text: "Merged PR on a widely-used async runtime library.",
      },
      {
        id: "s2",
        kind: "mention",
        source: "hn",
        at: iso(30),
        text: "Named in a thread about the next generation of infra tools.",
      },
    ],
    applications: [],
    outreach_draft:
      "Hi Kai — we track systems-level contributors closely. If a company idea is forming, we'd like to be an early conversation. No pitch needed. — MG",
  },
  f_mira: {
    id: "f_mira",
    headline: "B2B SaaS, founder+one, technical team.",
    location: "Toronto, CA",
    bio: "Two technical co-founders. Product cites $50K MRR; one claim currently marked contradicted vs. public HN post from 21 days earlier.",
    score_history: history([50, 54, 57, 59, 60, 61, 61, 61]),
    signals: [
      {
        id: "s1",
        kind: "deck",
        source: "inbound",
        at: iso(3),
        text: "Deck cites $50K MRR at 6 weeks post-launch — extractor flagged as contradicted.",
      },
      {
        id: "s2",
        kind: "post",
        source: "hn",
        at: iso(24),
        text: "Comment: 'pre-revenue, waitlist only — targeting Q3 launch.' Same author.",
      },
    ],
    applications: [
      {
        id: "app_mira_1",
        company: "Chen & Co",
        status: "screening",
        submitted_at: iso(3),
      },
    ],
    outreach_draft:
      "Hi Mira — we'd like to move Chen & Co into a first call. Ahead of that, we noticed one of the deck's revenue claims doesn't reconcile against a public post from three weeks earlier. We'd rather understand the sequence in a conversation than let it sit in the notes. — MG",
  },
  f_ao: {
    id: "f_ao",
    headline: "Cold-start entry. Low evidence density.",
    location: "Unknown",
    bio: "Synthetic enrichment stub. Name-only mention in a public thread; no corroborating source yet.",
    score_history: history([59, 59, 59, 59, 59, 59, 59, 59]),
    signals: [
      {
        id: "s1",
        kind: "mention",
        source: "synthetic",
        at: iso(18),
        text: "Named in a comment on an unrelated HN thread. No handle, no link.",
      },
    ],
    applications: [],
    outreach_draft:
      "(no outreach — insufficient evidence to personalize; run enrichment before drafting)",
  },
  f_lars: {
    id: "f_lars",
    headline: "3y of HN comment history, no shipped product.",
    location: "Copenhagen, DK",
    bio: "Long tail of thoughtful HN comments across 3 years. No product ships; ideation-stage signal.",
    score_history: history([62, 60, 58, 56, 55, 54, 54, 54]),
    signals: [
      {
        id: "s1",
        kind: "post",
        source: "hn",
        at: iso(9),
        text: "Comment: switched target market for the third time this quarter.",
      },
      {
        id: "s2",
        kind: "post",
        source: "hn",
        at: iso(70),
        text: "Original 'Ask HN' about the same idea, different framing.",
      },
    ],
    applications: [],
    outreach_draft:
      "Hi Lars — you write publicly about a space we care about. Would you be up for a low-stakes conversation? — MG",
  },
  f_synth2: {
    id: "f_synth2",
    headline: "Synthetic enrichment stub. Unverified.",
    location: "Unknown",
    bio: "Single inbound touch three weeks ago. No corroborating source; do not treat as verified.",
    score_history: history([47, 47, 47, 47, 47, 47, 47, 47]),
    signals: [
      {
        id: "s1",
        kind: "mention",
        source: "synthetic",
        at: iso(21),
        text: "Inbound form entry, unverifiable identity.",
      },
    ],
    applications: [],
    outreach_draft:
      "(no outreach — insufficient evidence to personalize; run enrichment before drafting)",
  },
};
