# The VC Brain

An AI-assisted venture screening system for the challenge **"The VC Brain: Deploying $100K Checks in 24 Hours"**.

The product helps a human investment reviewer move from a raw startup profile to an evidence-backed investment memo, an adversarial counter-case, and a final approval decision. It does **not** autonomously invest. It accelerates sourcing, research, screening, and memo preparation while keeping the $100K deployment decision human-approved.

## Core Idea

The VC Brain turns a startup into an investable decision packet:

1. Ingest a startup URL, pitch deck text, founder names, or a short company description.
2. Crawl the web for verifiable evidence about the company, founders, market, traction, competitors, and risks.
3. Store every extracted fact in shared Memory with an `evidence_id`, source URL, timestamp, confidence, and quote/snippet.
4. Score the startup across venture screening axes.
5. Write an investment memo using only cited evidence from Memory.
6. Run one bounded devil's advocate LLM pass, selected by the weakest screening axis.
7. Route each adversarial objection back through the same truth-gap Judge used for normal claim verification.
8. Give every objection a badge: `verified`, `unverified`, or `speculation`.
9. Optionally generate a short non-authoritative AI brief summarizing whether the verified objections appear decision-changing.
10. Present the memo, verified counter-case, optional brief, and source evidence side by side for human approval.

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
Frontend
  |
  |  Startup intake, progress view, memo review, final approve/reject
  v
Backend API
  |
  |  Orchestrates jobs, auth, persistence, status, API contracts
  v
AI Service
  |
  +-- Research Planner
  +-- Web Crawling Workers
  +-- Evidence Extractor
  +-- Memory Store
  +-- Screening Scorer
  +-- Memo Writer
  +-- Devil's Advocate
  +-- Truth-Gap Judge
  +-- Optional Verdict Brief
  +-- Final Decision Packet Builder
```

### Frontend

The frontend is the command center for a reviewer. It should support:

- Deal intake: company name, URL, short description, founder names, optional deck text.
- Live research progress: crawler status, discovered sources, extracted evidence count.
- Screening dashboard: Founder, Market, Product, Traction, Business Model, Fundraising, and Risk scores.
- Memo view: investment thesis, evidence-backed rationale, risks, missing information, recommendation.
- Counter-case view: adversarial objections with `verified`, `unverified`, or `speculation` badges.
- Optional AI brief: a compact, non-authoritative summary of whether verified objections look decision-changing.
- Human action: approve, reject, request more research, or mark as watchlist.

### Backend

The backend owns orchestration and persistence. It should:

- Accept deal intake from the frontend.
- Create deal, research, memo, adversary, truth-gap verification, and optional verdict-brief jobs.
- Store all normalized outputs.
- Expose stable APIs for frontend and AI service.
- Enforce job state transitions.
- Keep the final decision human-controlled.

### AI Service

The AI service owns the intelligence pipeline. It should expose deterministic, versioned endpoints so the backend can run each stage independently.

The AI service stages are:

1. `research.plan`: generate targeted web research tasks.
2. `research.crawl`: crawl and fetch source pages.
3. `evidence.extract`: convert pages into structured facts.
4. `screen.score`: score the company across screening axes.
5. `memo.write`: write the investment memo from Memory.
6. `adversary.write`: write the strongest case against investing.
7. `truth_gap.verify`: reuse the truth-gap Judge to badge each adversarial objection.
8. `verdict.brief`: optionally summarize whether verified objections look decision-changing for the human reviewer.
9. `packet.build`: produce final reviewer-ready output.

## Memory And Evidence

Memory is the shared source of truth between all LLM calls. Every factual statement used by the memo, adversary, truth-gap Judge, and optional verdict brief must trace back to Memory.

Each Memory item has:

- `evidence_id`: stable ID like `ev_001`.
- `deal_id`: deal being evaluated.
- `source_url`: original source.
- `source_title`: source title if available.
- `captured_at`: timestamp.
- `claim`: normalized factual statement.
- `quote`: source snippet supporting the claim.
- `evidence_type`: `company`, `founder`, `market`, `traction`, `competition`, `fundraising`, `risk`, or `unknown`.
- `confidence`: `low`, `medium`, or `high`.
- `freshness`: `current`, `stale`, or `unknown`.

Rules:

- The memo cannot make uncited factual claims.
- The adversary cannot invent facts.
- Every adversarial objection must cite an `evidence_id` or be labeled `speculation`.
- Speculation is allowed only as risk reasoning, not as a factual assertion.
- The truth-gap Judge badges objections with missing, irrelevant, or contradicted evidence as `unverified`.

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
- De-duplicate identical or near-identical content.
- Prefer primary sources when available.
- Label stale or low-confidence evidence.
- Never let the crawler's summary replace source-backed Memory.

## Screening Axes

The screening scorer returns normalized scores from `0` to `100`.

Recommended axes:

- `founder`: track record, domain fit, credibility, execution signals.
- `market`: market size, timing, growth, urgency, buyer pain.
- `product`: clarity, differentiation, technical defensibility, UX/product proof.
- `traction`: revenue, customers, usage, pilots, retention, growth rate.
- `business_model`: pricing, margins, sales motion, repeatability.
- `fundraising`: prior funding, round fit, valuation plausibility, investor signal.
- `risk`: legal, regulatory, reputational, technical, concentration, execution risk.

The weakest axis selects the counter-case lens. This is not a personality or a debate role; it is just the area the single devil's advocate pass should stress-test most.

- Weak `founder` -> focus the counter-case on founder risk.
- Weak `market` -> focus the counter-case on market risk.
- Weak `product` -> focus the counter-case on product risk.
- Weak `traction` -> focus the counter-case on traction risk.
- Weak `business_model` -> focus the counter-case on business-model risk.
- Weak `fundraising` -> focus the counter-case on financing and round-fit risk.
- Weak `risk` -> focus the counter-case on legal, regulatory, reputational, and execution risk.

Tie-breaker order is: `risk`, `founder`, `traction`, `market`, `product`, `business_model`, `fundraising`. This keeps the system deterministic.

## LLM Pipeline

### LLM 1: Research Planner

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

### LLM 2: Evidence Extractor

Input:

- Crawled page text.
- Page URL and metadata.

Output:

- Structured Memory records.

Goal:

Extract only evidence-backed claims. If a page is irrelevant or too weak, return no evidence.

### LLM 3: Screening Scorer

Input:

- Deal intake.
- All Memory records.

Output:

- Axis scores.
- Rationale per axis.
- Missing evidence per axis.
- Weakest axis.

Goal:

Produce a transparent quantitative screen without pretending certainty.

### LLM 4: Memo Writer

Input:

- Deal intake.
- Memory records.
- Screening scores.

Output:

- Investment memo.
- Recommendation: `approve`, `reject`, `needs_more_research`, or `watchlist`.
- Required evidence citations.

Goal:

Write the strongest honest investment case supported by Memory.

### LLM 5: Devil's Advocate

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

### LLM 6: Truth-Gap Judge On Adversarial Objections

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

### Optional LLM 7: Verdict Brief

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

- Deal summary.
- Screening scores.
- Investment memo.
- Source-backed evidence table.
- Devil's advocate counter-case.
- Truth-gap badges for each adversarial objection.
- Optional non-authoritative verdict brief.
- Clear approve/reject/watchlist/needs-more-research recommendation.
- Human decision buttons.
- Human verdict audit log: reviewer, timestamp, decision, and notes.

The final product should feel like a VC analyst team compressed into a fast, auditable workflow.

## Parallel Development Plan

### Frontend Team

Use `api-contract.json` as the source of truth.

Build:

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

1. Reviewer enters startup name, URL, and short description.
2. Backend creates a deal and starts the research job.
3. Frontend shows live progress while crawler and evidence extraction run.
4. Screening scores appear with weakest axis highlighted.
5. Memo is generated from cited Memory.
6. Devil's advocate report is generated using the weakest-axis counter-case lens.
7. The truth-gap Judge badges each adversarial objection as `verified`, `unverified`, or `speculation`.
8. Optional verdict brief summarizes the strongest verified objections for faster human review.
9. Reviewer sees the final decision packet and approves/rejects the $100K check.

## Success Criteria

- A judge can understand why the system recommends investing or not investing.
- Every important factual claim has a source.
- The counter-case is strong but bounded.
- The truth-gap Judge catches hallucinated or unsupported adversarial attacks.
- The optional verdict brief helps the reviewer scan the counter-case without replacing human judgment.
- Frontend, backend, and AI service can be developed in parallel from the shared API contract.
