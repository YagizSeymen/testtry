# AI Service

The AI lane for VentureIntelligence. The product contract is
[`../api-contract.json`](../api-contract.json); [`../steps.md`](../steps.md) is
the behavioral source of truth.

## Boundary

The backend owns SQLite Memory, founder identity and score persistence, all
`/api` routes, the deterministic Decision Brief, audit/metrics, and the human
decision. This service owns only the bounded analysis calls and can be used in
two equivalent ways:

- import the functions in `ai_service.pipeline` from the backend process; or
- run this server and call its internal `/v1/ai/*` endpoints.

The frontend must never call this service directly.

## Fixed DAG

`run_application_pipeline` is a LangGraph state machine:

```text
extract [Luna]
  -> screen, 3 independent axes [Terra]
  -> diligence, per-claim truth-gap [Terra]
  -> memo, committed claims only [Terra]
  -> adversary, one pass [Terra]              optional P1
  -> adversary verification, one batch [Terra] optional P1
  -> backend deterministic Decision Brief
  -> human approve or reject
```

There is no swarm, agent conversation, debate loop, or AI winner declaration.
The human gate is outside the graph.

## Internal endpoints

All are `POST` under `/v1/ai` and have exact schemas in `api-contract.json`:

- `/extract`
- `/query`
- `/screen`
- `/diligence`
- `/memo`
- `/adversary`
- `/adversary/verify`
- `/application/run` (integration helper for the fixed DAG)

The existing research, crawler, sourcing, and legacy `/v1/ai/*` helpers remain
available while the backend is being wired. They are not product-contract
routes and must not be used by the frontend.

## Guardrails

- The extractor treats decks as untrusted data, requires an exact source span,
  retries once, then leaves a failed claim's span null.
- A null-span claim cannot become supported or appear in `recommendation.based_on`.
- The judge resolves IDs against supplied Memory Signals before applying trust.
- The adversary persona is deterministic from the weakest of the three axes.
- An adversarial objection without valid evidence is converted to speculation;
  the judge verifies all evidence-backed objections in one batch.
- The service returns no chain-of-thought and makes no investment decision.

## Models and modes

`gpt-5.6-luna` handles extraction and query parsing. `gpt-5.6-terra` handles
screening, diligence, memo writing, the counter-case, and its verification.

Deterministic mode is the default and requires no key. It is used for fixtures,
tests, and parallel backend/frontend work. Model mode is opt-in:

```bash
python3 -m pip install -r ai_service/requirements.txt
export VC_BRAIN_LLM_MODE=openai
export OPENAI_API_KEY=your_key_here
python3 -m ai_service.server --port 8001
```

## Test

```bash
python3 -m unittest discover -s ai_service/tests
```
