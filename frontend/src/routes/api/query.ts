import { createFileRoute } from "@tanstack/react-router";
import { FOUNDERS, matchQuery } from "@/lib/dashboard-data";

export type ParsedQuery = {
  technical_founder: boolean | null;
  sectors: string[] | null;
  geos: string[] | null;
  shipped_within_days: number | null;
  prior_vc: boolean | null;
};

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

export function parseQuery(q: string): ParsedQuery {
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

export const Route = createFileRoute("/api/query")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const body = (await request.json().catch(() => ({}))) as {
          q?: string;
        };
        const q = (body.q ?? "").trim();
        const parsed = parseQuery(q);
        const results = FOUNDERS.map((f) => ({
          founder: f,
          why_matched: matchQuery(q, f),
        }))
          .filter((r) => r.why_matched.length > 0)
          .sort((a, b) => b.founder.score - a.founder.score);
        return Response.json({ q, parsed, results });
      },
    },
  },
});
