# FirstCheck

FirstCheck is a venture-intelligence workspace for the VC Brain hackathon. It
turns thesis-driven public-web founder discovery, reviewed fallback signals, and inbound application
decks into an evidence-linked investment workflow. A human makes the final
$100K decision.

The product implements the frozen API and pipeline in [`steps.md`](steps.md):

1. Discover technical founders through reviewed Memory signals.
2. Activate an outbound candidate with a review-only outreach draft.
3. Process a real inbound deck through extraction, screening, diligence, memo,
   one adversarial counter-case, batched verification, and a Decision Brief.
4. Show the memo, verified objections, cited evidence, and audit trail to the
   human reviewer before approval or rejection.

There is deliberately no agent debate, swarm, or automated winner. The
adversary writes once; the truth-gap judge verifies every objection against
Memory; the human gate decides.

## Run Locally

Prerequisites: Python 3.11+ and Node.js 20+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
make dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). The FastAPI OpenAPI UI is
available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

`make dev` starts both services and leaves the seeded reviewed cache available
without credentials or network access. The backend uses SQLite at
`backend/venture_intelligence.db`; deleting that local file resets the demo.

Useful commands:

```bash
make seed  # load the reviewed cache into SQLite
make scan  # run the thesis-driven live scan (with cache fallback)
make eval  # run deterministic AI-service tests
```

## OpenAI-Backed Mode

The default is deliberately deterministic and requires no API key. To run the
bounded stages through OpenAI instead, create a root `.env` file from the
checked-in template:

```bash
cp .env.example .env
```

Set these values in `.env`:

```bash
OPENAI_API_KEY=your_key_here
VC_BRAIN_LLM_MODE=openai
```

Then install the full runtime dependencies and start the app:

```bash
.venv/bin/pip install -r backend/requirements.txt
make dev
```

`.env` is ignored by Git. Never put the API key in `frontend/.env.local`, a
`NEXT_PUBLIC_*` variable, a committed file, or a client-side request. The API
key is read only by the FastAPI process. The router uses `gpt-5.6-luna` for
extract/query work and `gpt-5.6-terra` for evidence reasoning and memo stages.

## Public Demo Deployment

### Vercel

[`vercel.json`](vercel.json) deploys the Next.js frontend and FastAPI backend
as two Vercel Services under one public domain. Requests to `/api/*` are routed
to FastAPI; all other requests go to Next.js. This keeps the browser on a
same-origin API and keeps `OPENAI_API_KEY` server-side.

1. In Vercel, import `YagizSeymen/testtry` and select the repository root as
   the Root Directory.
2. Set the project framework to **Services** (Vercel's current multi-service
   deployment mode) and leave the build/output commands at their defaults.
3. Add these existing server-side environment variables for Preview and
   Production:

   ```text
   OPENAI_API_KEY = your_key_here
   VC_BRAIN_LLM_MODE = openai
   ```

   Omit both variables to use the deterministic, no-key demo mode. Never add
   the key as `NEXT_PUBLIC_*` or to the frontend service.
4. Deploy, then verify `https://<your-domain>/api/metrics` before opening the
   application.

Vercel functions have no durable local disk. The deployment therefore stores
SQLite in `/tmp` and reseeds the reviewed cache on each cold start; changes made
during a warm demo session are available to that instance only. This is suitable
for the hackathon demo. For durable multi-user data, use a managed Postgres
database before relying on the deployment for real investor workflows.

### Render

This repository includes a single-container public-demo configuration:

- [`Dockerfile`](Dockerfile) builds a static Next.js client and serves it from
  FastAPI, so browser requests and `/api` share one public origin.
- [`render.yaml`](render.yaml) configures a Render web service with a persistent
  disk mounted at `/data` for the SQLite demo database and uses `/api/metrics`
  as its health check.

To deploy it on Render, push this branch to GitHub, create a new Blueprint from
the repository, and set these **server-side** environment variables in the
Render dashboard:

```text
OPENAI_API_KEY = your_key_here
VC_BRAIN_LLM_MODE = openai
```

Do not set either value in `render.yaml` or expose it to the frontend. The
deployment is suitable for a public hackathon demo. It is not yet a
production-grade multi-user service: it still needs authentication, rate
limits and spend controls, database migrations/Postgres, durable job handling,
and operational monitoring before handling real investor or founder data.

## Product Flow

- **Discovery:** edit the server-side thesis, then use the refresh control to
  run a bounded live scan. `Luna` uses OpenAI web search to find candidates;
  the service crawls at most 12 cited public URLs, retains source-linked
  evidence, and promotes only candidates that meet the evidence threshold and
  have no public funding evidence in the searched corpus. A natural-language
  query then filters the retained Memory. Founder scores are deterministic,
  carry an uncertainty band, and follow the person rather than the company.
- **Outbound:** select a founder and use **Activate** to produce a draft. This
  does not create an investment memo; a submitted deck starts the formal flow.
- **Inbound:** use **New application** with a company name and deck text. The
  extractor resolves the founder by normalized name, so an activated founder
  and their later application converge on one record.
- **Review:** run Screen, Diligence, Memo, and Counter-case in order. The
  counter-case is labelled `verified`, `unverified`, or `speculation` and
  cannot invent evidence. The deterministic Decision Brief summarizes contested
  claim/objection pairs for human review.

The reviewed fallback cache contains GitHub, Hacker News, and explicitly
labelled synthetic signals. It keeps the P0 workflow available without network
access. Live data is visibly marked by its public-web, GitHub, or HN provenance;
absence of public funding evidence is never presented as proof of no funding.

## Architecture

```text
Next.js workspace
          |
          v
FastAPI + SQLite <-------------------- reviewed cache fallback
          |
          v
LangGraph sourcing: plan -> Luna web search -> bounded cited-source crawl
          |                                      (12 public URLs max)
          v
Evidence-gated Memory -> inbound application workflow -> human decision
```

The backend owns API validation, durable state, person-level identity,
deterministic score/trust/decision calculations, and audit logging. The AI
service owns bounded model stages and deterministic fallbacks. Model-backed
mode uses the configured `gpt-5.6-luna` and `gpt-5.6-terra` routing; without an
API key, the same typed pipeline runs from its deterministic fallback.

## Guardrails

- Deck text is untrusted data. Claims with a source span must quote an exact
  substring of the submitted deck.
- Every adversarial objection is run back through the same evidence judge.
- All recommendations remain advisory. Only `POST /api/decisions/{id}/decide`
  records a decision, with an approver in the audit trail.
- Existing request and response shapes are frozen by `steps.md` section 3.

## What's Next

- Replace demo-only normalized-name matching with stronger entity resolution.
  The current rule intentionally accepts name-collision risk and seeded data
  guarantees unique names.
- Add source-specific GitHub and Hacker News connectors only when they provide
  material signal quality beyond the current cited public-web crawler.
