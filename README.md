# The VC Brain

An AI-assisted venture screening system for the challenge **"The VC Brain: Deploying $100K Checks in 24 Hours"**.

The product helps a human investment reviewer discover exceptional founders before fundraising, accept inbound applications, and move either path to an evidence-backed memo, a bounded counter-case, and a final human approval decision. It does **not** autonomously invest. It accelerates sourcing, research, screening, and memo preparation while keeping the $100K deployment decision human-approved.

## Core Idea

The VC Brain has two entry paths that converge into one investable decision packet:

1. **Outbound sourcing:** an investor sets a thesis, then the system searches public GitHub, launches, hackathons, papers/patents, accelerator cohorts, and funding sources for source-backed candidates.
2. **Inbound application:** a founder submits at least a company name and deck, with optional URL and founder fields.
3. Both paths crawl and normalize verifiable evidence into persistent Memory with an `evidence_id`, source URL, timestamp, Trust Score, and quote/snippet.
4. Founder Memory maintains a persistent Founder Score across applications and milestones; a sparse public footprint is a low-confidence cold start, never a negative founder fact.
5. Screen the opportunity independently on Founder, Market, and Idea vs. Market axes, with an explicit trend for each. They are never averaged into one decision number.
6. Write an evidence-backed investment memo using only cited Memory and explicitly marking unavailable data.
7. Run one bounded devil's advocate pass, selected by the weakest decision lens.
8. Route each adversarial objection back through the same truth-gap Judge used for normal claim verification.
9. Give every objection a badge: `verified`, `unverified`, or `speculation`.
10. Optionally generate a short non-authoritative AI brief, then present memo, counter-case, claim Trust Scores, and source evidence for human approval.

The architecture keeps the exceptional part focused: strong evidence collection, transparent reasoning, and bounded adversarial review. It avoids an unstable multi-agent debate loop.

## What We Are Not Building

We are not building a swarm, open-ended agent society, or agents arguing with each other until consensus. Multi-agent debate is risky in a short hackathon because it can become hard to debug, slow to demo, and indistinguishable to judges from a simpler pipeline.

Instead, the system uses a **bounded multi-judge pattern**:

- One memo writer produces the invest case.
- One adversary produces the strongest case against investing.
- The same truth-gap Judge verifies whether each adversarial objection is evidence-grounded.
- An optional AI brief can summarize the strongest verified objections for reviewer convenience.
- The human reviewer sees all outputs and makes the final decision.

This gives us adversarial rigor without a fragile debate loop.

## Architecture

```text
Investor Thesis Engine                 Inbound Application
  | sectors, geography, risk             | company name + deck minimum
  v                                      v
Outbound Sourcing ----------------> Shared Memory <---------------- Inbound Research
  | web search, crawler, entity          | sources, evidence, Founder Score,
  | resolution, candidate ranking        | trust/contradiction history
  +------------------------------+-------+
                                 v
                      Three-Axis Intelligence
                Founder | Market | Idea vs. Market
                                 v
               Memo -> one Counter-Case -> Truth-Gap Judge
                                 v
                         Human $100K Decision
```

### Frontend

The frontend is the command center for a reviewer. It should support:

- Deal intake: company name, URL, short description, founder names, optional deck text.
- Live research progress: crawler status, discovered sources, extracted evidence count.
- Screening dashboard: the three decision axes (Founder, Market, Idea vs. Market), with product, traction, business model, fundraising, and risk retained as supporting diagnostics.
- Memo view: investment thesis, evidence-backed rationale, risks, missing information, recommendation.
- Counter-case view: adversarial objections with `verified`, `unverified`, or `speculation` badges.
- Optional AI brief: a compact, non-authoritative summary of whether verified objections look decision-changing.
- Human action: approve, reject, request more research, or mark as watchlist.

### Backend

The backend owns orchestration and persistence. It should:

- Accept deal intake from the frontend.
- Persist versioned theses, sourcing jobs, candidates, activation state, normalized Memory, deal jobs, and source-channel outcomes.
- Create research, memo, adversary, truth-gap verification, and optional verdict-brief jobs.
- Store all normalized outputs.
- Expose stable APIs for frontend and AI service.
- Enforce job state transitions.
- Record human decisions against the decision-packet version and operational audit events without persisting chain-of-thought.
- Keep the final decision human-controlled.

### AI Service

The AI service owns the intelligence pipeline. It should expose deterministic, versioned endpoints so the backend can run each stage independently.

The AI service stages are:

1. `sourcing.plan`: turn a Thesis Engine request into transparent outbound queries.
2. `research.crawl`: crawl an explicit bounded list of public source pages.
3. `sourcing.discover`: resolve source-backed founder/company candidates from crawler documents or cited web search.
4. `sourcing.rank`: assess candidate evidence coverage and thesis eligibility before a human activation decision.
5. `founders.memory.*`: create provisional identity references and persist Founder Score evidence, milestones, and history across applications.
6. `research.plan`: generate targeted research tasks for a known inbound or activated deal.
7. `evidence.extract` and `evidence.verify`: convert pages into facts, assign per-claim Trust Scores, and flag contradictions.
8. `screen.score`: score the opportunity independently on Founder, Market, and Idea vs. Market axes.
9. `memo.write`: write the required investor memo sections from Memory while marking data gaps.
10. `adversary.write`, `truth_gap.verify`, and optional `verdict.brief`: produce and verify one bounded counter-case for the human reviewer.

## Sourcing And Founder Discovery

Sourcing is a first-class product path, not a search box attached to diligence.
The investor configures a Thesis Engine with natural-language criteria plus
sector, geography, stage, check size, ownership target, and risk appetite. The
AI service expands that thesis into explicit query families, including GitHub
and open-source execution, launches/product traction, hackathons, papers or
patents, accelerator cohorts, and public funding sources.

For example, the system can run one thesis such as:

> Find technical founders in Europe working on AI infrastructure who have strong execution signals, no previous VC funding, and evidence of product traction.

The result is a ranked candidate list with source-backed eligibility records,
not an investment decision. Each candidate can then be activated to apply or
converted to a normal deal intake and passed through the same diligence flow as
an inbound application.

`no previous VC funding` is handled carefully: the system can report **no public
funding evidence found in the searched corpus**, but it cannot claim that no VC
funding exists. Every such candidate remains marked for human confirmation.

The outbound path is bounded:

1. Thesis planner writes a transparent query plan.
2. Web search returns cited candidate leads, or backend-provided crawler documents are used in deterministic mode.
3. The crawler fetches only an explicit, capped list of public pages, rejects local/private network targets, checks `robots.txt`, rate-limits by host, and preserves source metadata.
4. Candidate evidence is extracted and deduplicated by source, signal, and claim.
5. A deterministic eligibility rank checks evidence coverage against the thesis.
6. Only the top candidates enter the heavier deal-diligence graph.

## Founder Memory And Cold Start

Founder Memory persists an evidence-backed profile keyed by founder identity:

- Founder Score, confidence, trend, and score history.
- Milestones such as an open-source release, launch, paper, patent, or hackathon result.
- Exact evidence IDs behind each factor.
- Provisional identity metadata (`founder_id`, aliases, resolution confidence) so normalized-name matches are not mistaken for certain entity resolution.

The Founder Score is one input to the opportunity's **Founder** axis; it never
replaces the three-axis opportunity assessment. For a first-time founder with
no public GitHub, funding, or network record, the score starts as a neutral,
low-confidence provisional score. Missing public data becomes a diligence gap,
not a proxy for lack of ability. New evidence and founder-submitted milestones
update the profile over time.

## Memory And Evidence

Memory is the shared source of truth between all LLM calls. Every factual statement used by the memo, adversary, truth-gap Judge, and optional verdict brief must trace back to Memory.

Each Memory item has:

- `evidence_id`: stable ID like `ev_001`.
- `deal_id`: deal being evaluated.
- `candidate_id` / `founder_id`: optional cross-funnel associations for the same normalized Memory claim.
- `source_url`: original source.
- `source_title`: source title if available.
- `captured_at`: timestamp.
- `published_at`, canonical URL, source channel, and content hash where available.
- `claim`: normalized factual statement.
- `quote`: source snippet supporting the claim.
- `evidence_type`: `company`, `founder`, `market`, `traction`, `competition`, `fundraising`, `risk`, or `unknown`.
- `confidence`: `low`, `medium`, or `high`.
- `trust_score`: per-claim score from source quality, corroboration, and contradictions.
- `trust_status`: `unverified`, `internally_consistent`, `externally_verified`, or `contradicted`.
- `freshness`: `current`, `stale`, or `unknown`.

Rules:

- The memo cannot make uncited factual claims.
- The adversary cannot invent facts.
- Every adversarial objection must cite an `evidence_id` or be labeled `speculation`.
- Speculation is allowed only as risk reasoning, not as a factual assertion.
- The truth-gap Judge badges objections with missing, irrelevant, or contradicted evidence as `unverified`.
- Claim validation runs before screening; direct contradictions reduce the affected claim's Trust Score and are visible to the reviewer.

## Research And Crawling

The web crawling layer gathers external context fast, but controlled.

Recommended crawler tasks:

- Company website and product pages.
- Founder LinkedIn/public bios/GitHub/past companies.
- Funding announcements and investor pages.
- Product reviews, launch pages, app stores, or public demos.
- Competitor websites and market category pages.
- News, regulatory, legal, and reputational risk signals.

Crawler outputs should be raw HTML/text plus metadata. The LLM should not reason directly from untracked pages. First, the Evidence Extractor converts crawled content into Memory records.

Crawler guardrails:

- Respect robots and rate limits.
- Store source URLs and timestamps.
- Preserve canonical URLs, response-content hashes, source channel, and a backend raw-document reference when retention is permitted.
- De-duplicate identical or near-identical content.
- Prefer primary sources when available.
- Label stale or low-confidence evidence.
- Never let the crawler's summary replace source-backed Memory.

## Screening Axes

The decision layer shows exactly three independent, **non-averaged** opportunity
axes. Each exposes `bullish`, `neutral`, or `bear`, a trend, supporting evidence
IDs, and explicit gaps:

- `founder`: track record, domain fit, execution signals, and the persistent Founder Score.
- `market`: market size, urgency, timing, competition, and buyer context.
- `idea_market`: whether the product, traction, and business model survive market scrutiny as-is, or whether the team would need to pivot.

Supporting diagnostics for product, traction, business model, fundraising, and
risk remain visible, but do not become a single overall score. The decision
recommendation explains the three axes rather than averaging them.

The weakest of the three decision axes deterministically selects the
counter-case focus. This is not a personality or a debate role; it is the
functional area the single devil's advocate pass should stress-test.

- Weak `founder` -> founder/track-record evidence.
- Weak `market` -> market and competitive evidence.
- Weak `idea_market` -> product, traction, and business-model evidence.

Tie-breaker order is `founder`, `market`, `idea_market`. Supporting diagnostics
remain visible, but they do not replace the three-axis decision frame.

## LLM Pipeline

Each label below is a fixed stage, not a conversational agent. LangGraph owns
the bounded state transitions; there is no debate loop or autonomous swarm.

### LLM 1: Thesis And Sourcing Planner

Input:

- Investor thesis: sector, geography, stage, check size, ownership target, and risk appetite.
- Natural-language required signals.

Output:

- Explicit query plan across GitHub, launches, hackathons, papers/patents, accelerators, and funding sources.
- Candidate eligibility criteria and limitations.

Goal:

Make outbound discovery inspectable and thesis-specific before any web search happens.

### LLM 2: Candidate Discovery

Input:

- Approved sourcing query plan.
- Public-web search tool results with URL citations, or crawler documents in deterministic mode.

Output:

- Candidate companies/founders and source-backed execution, technical, location, traction, and funding signals.

Goal:

Find leads before fundraising without treating missing public data as a negative fact. The `no previous VC funding` condition is always a human-confirmation state, never a web-search assertion.

### LLM 3: Deal Research Planner

Input:

- Deal intake.
- Known company/founder fields.

Output:

- Search queries.
- Target URLs if known.
- Research priorities.
- Expected evidence types.

Goal:

Create a fast plan for what the crawlers should fetch.

### LLM 4: Evidence Extractor

Input:

- Crawled page text.
- Page URL and metadata.

Output:

- Structured Memory records.

Goal:

Extract only evidence-backed claims. If a page is irrelevant or too weak, return no evidence.

### LLM 5: Claim Trust Validator

Input:

- Structured Memory evidence from all crawled sources.

Output:

- Per-claim Trust Scores, verification status, and directly contradicted evidence IDs.

Goal:

Run the same truth-gap discipline on normal claims before screening and memo generation.

### LLM 6: Screening Scorer

Input:

- Deal intake.
- All Memory records.

Output:

- Three independent Founder, Market, and Idea vs. Market outlooks and trends.
- Rationale per axis.
- Missing evidence per axis.
- Weakest counter-case lens.

Goal:

Produce a transparent non-averaged screen without pretending certainty.

### LLM 7: Memo Writer

Input:

- Deal intake.
- Memory records.
- Screening scores.

Output:

- Company snapshot, hypotheses, SWOT, problem/product, traction & KPIs, diligence log, and explicit data gaps.
- Recommendation: `approve`, `reject`, `needs_more_research`, or `watchlist`.
- Required evidence citations.

Goal:

Write the strongest honest investment case supported by Memory.

### LLM 8: Devil's Advocate

Input:

- Final memo.
- Screening scores.
- All Memory records.
- Deterministically selected counter-case lens.

Output:

- Strongest case against investing.
- Objections with cited `evidence_id`s or `speculation` labels.
- Severity per objection.
- Suggested diligence questions.

Goal:

Red-team the investment case without becoming a debate agent.

Important constraints:

- One pass only.
- No arguing back.
- No new crawling.
- No invented facts.
- Every objection must be evidence-backed or explicitly marked as speculation.

### LLM 9: Truth-Gap Judge On Adversarial Objections

Input:

- Devil's advocate report.
- Memory records.
- Memo.

Output:

- Verification badge for each objection: `verified`, `unverified`, or `speculation`.
- Hallucination check.
- Evidence relevance check.
- Contradiction check.
- Corrected version if the objection is directionally right but overstated.

Goal:

Reuse the existing truth-gap Judge to determine whether the red-team attacks are legitimate and grounded. An objection is treated as another claim against Memory, not as a separate agent debate.

Truth-gap Judge rules:

- If an objection cites evidence that supports it, badge it `verified`.
- If an objection cites evidence that does not support it, badge it `unverified`.
- If an objection adds a factual claim without evidence, badge it `unverified` unless it is clearly labeled speculation.
- If an objection is explicitly risk reasoning from missing or weak evidence, badge it `speculation`.
- If an objection contradicts stronger evidence in Memory, badge it `unverified` and cite the contradictory evidence.

### Optional LLM 10: Verdict Brief

Input:

- Memo.
- Devil's advocate report with truth-gap badges.
- Screening scores.
- Memory records.

Output:

- A short, non-authoritative reviewer brief.
- Most important verified objections.
- Speculative objections worth diligence.
- Suggested human review focus.
- Suggested decision impact: `none`, `minor`, `major`, or `blocking`.

Goal:

Make the human review easier without letting an LLM declare the winner. The brief can say "these objections may be decision-changing," but the final verdict belongs to the human reviewer.

This stage is optional. For a faster or more conservative demo, the product can skip it and show the memo plus verified attacks directly.

## Final Decision Packet

The reviewer should see:

- Thesis criteria and the outbound/inbound origin of the opportunity.
- Persistent Founder Score, confidence, trend, milestones, and uncertainty.
- Deal summary.
- Three independent screening axes with outlook and trend, plus supporting diagnostics.
- Investment memo with Company Snapshot, Investment Hypotheses, SWOT, Problem & Product, Traction & KPIs, and an explicit diligence log/data gaps.
- Source-backed evidence table with per-claim Trust Scores and contradictions.
- Devil's advocate counter-case.
- Truth-gap badges for each adversarial objection.
- Optional non-authoritative verdict brief.
- Clear approve/reject/watchlist/needs-more-research recommendation.
- Human decision buttons.
- Human verdict audit log: reviewer, timestamp, decision, and notes.
- Operational stage trace: model/stage/version and input/output record IDs only, never model chain-of-thought.

The final product should feel like a VC analyst team compressed into a fast, auditable workflow.

## Parallel Development Plan

### Frontend Team

Use `api-contract.json` (`0.4.0`) as the source of truth. It separates a
pre-deal `SourcingJob` from a deal `Job`, and defines thesis versions, identity
references, candidate activation, source provenance, audit events, and outcome
feedback so the three teams can work independently.

Build:

- Thesis configuration and outbound candidate-list views.
- Deal intake form.
- Deal status page.
- Evidence table.
- Screening dashboard.
- Memo and counter-case comparison view.
- Final decision actions.

Mock against the JSON response schemas until backend endpoints are ready.

### Backend Team

Use `api-contract.json` as the source of truth.

Build:

- Thesis, sourcing-run, candidate, Founder Memory, and source persistence.
- Deal persistence.
- Job orchestration.
- API endpoints.
- AI service client.
- Status polling.
- Final packet persistence.

Backend can initially return mock AI outputs matching the contract.

### AI Service Team

Use `api-contract.json` as the source of truth.

Build:

- Thesis planning, cited web discovery, bounded crawling, candidate resolution, and evidence-gated ranking.
- Persistent Founder Score updates and claim-level Trust Score validation.
- Research planning.
- Crawling adapter.
- Evidence extraction.
- Scoring.
- Memo generation.
- Devil's advocate generation.
- Truth-gap verification for adversarial objections.
- Optional verdict-brief generation.

Every AI endpoint should be callable independently so failures are isolated and easy to demo.

## Demo Flow

1. Investor configures a thesis or a founder submits a company name and deck.
2. Outbound discovery scans cited public signals, ranks candidates, and invites the strongest matches to apply; inbound and activated candidates converge into one deal funnel.
3. Backend starts bounded crawling and evidence extraction, while the frontend shows sources, candidate signals, and Founder Score updates.
4. Claim validation assigns Trust Scores and flags contradictions before screening.
5. Founder, Market, and Idea vs. Market appear independently with trend and evidence gaps.
6. The memo is generated from cited Memory and explicitly labels unavailable financial, cap-table, and diligence data.
7. Devil's advocate report is generated using the weakest-axis counter-case lens.
8. The truth-gap Judge badges each adversarial objection as `verified`, `unverified`, or `speculation`.
9. Optional verdict brief summarizes the strongest verified objections for faster human review.
10. Reviewer sees the final decision packet and approves/rejects the $100K check.

## Success Criteria

- A judge can understand why the system recommends investing or not investing.
- A judge can see thesis-driven outbound candidates before fundraising, with the exact GitHub, launch, hackathon, paper/patent, accelerator, or public-web signal that surfaced them.
- A first-time founder with sparse public evidence is handled as a transparent cold-start case, not discarded because they lack network visibility.
- Every important factual claim has a source.
- Every claim has a Trust Score and visible contradiction state.
- Founder, Market, and Idea vs. Market remain independent and are never collapsed into an average.
- The counter-case is strong but bounded.
- The truth-gap Judge catches hallucinated or unsupported adversarial attacks.
- The optional verdict brief helps the reviewer scan the counter-case without replacing human judgment.
- Frontend, backend, and AI service can be developed in parallel from the shared API contract.
