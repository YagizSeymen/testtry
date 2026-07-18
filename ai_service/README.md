# AI Service

AI service implementation for the bounded workflow described by `api-contract.json` (`0.4.0`).

## Run

```bash
python3 -m ai_service.server --port 8001
```

For the deterministic integration mode used by frontend/backend while they work
in parallel, no API key is required. To enable the model-backed runtime:

```bash
python3 -m pip install -r ai_service/requirements.txt
export VC_BRAIN_LLM_MODE=openai
export OPENAI_API_KEY=your_key_here
python3 -m ai_service.server --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/health
```

## Endpoints

All endpoints are under `/v1/ai`:

- `POST /sourcing/plan`
- `POST /research/crawl`
- `POST /sourcing/discover`
- `POST /sourcing/rank`
- `POST /sourcing/run`
- `POST /founders/memory/upsert`
- `POST /founders/memory/get`
- `POST /founders/memory/resolve`
- `POST /research/plan`
- `POST /evidence/extract`
- `POST /evidence/verify`
- `POST /screen/score`
- `POST /memo/write`
- `POST /adversary/write`
- `POST /truth-gap/verify`
- `POST /verdict/brief`

The service intentionally does not include a swarm, debate loop, or LLM winner-decider. It uses a single counter-case pass, verifies objections through the truth-gap Judge, and returns an optional non-authoritative verdict brief for human readability.

## Orchestration

The service uses LangGraph as a bounded state-machine orchestrator. It does not
use Google ADK or LangChain: neither is needed for this fixed, inspectable DAG.

```text
Investor thesis
  -> sourcing plan [Luna]
  -> cited web discovery [Luna] or supplied crawler documents
  -> persistent Founder Memory update
  -> evidence-gated candidate ranking [deterministic]
  -> human activation / inbound application

Known deal
  -> research plan [Luna]
  -> evidence extraction per source [Luna, parallel]
  -> Memory merge [barrier]
  -> claim Trust Score + contradiction validation [Terra]
  -> three independent axes: Founder | Market | Idea vs. Market [Terra]
  -> memo [Terra]
  -> one counter-case [Terra]
  -> truth-gap Judge [Terra]
  -> optional verdict brief [Luna]
  -> human decision outside the graph
```

`ai_service/sourcing_orchestration.py` implements the sourcing LangGraph used by
`POST /sourcing/run`; `ai_service/orchestration.py` implements deal diligence.
Crawler fetches and
document evidence extraction fan out only for independent URLs/pages, then merge
at Memory barriers. Candidate ranking, claim validation, screening, memo, and
adversarial review stay sequential because they depend on verified prior state.

## Model Routing

| Stage | Model | Reason |
| --- | --- | --- |
| Thesis and sourcing plan | `gpt-5.6-luna` | High-volume query decomposition |
| Candidate discovery | `gpt-5.6-luna` with web search | Cited public-web lead finding |
| Research plan | `gpt-5.6-luna` | High-volume query planning |
| Evidence extraction | `gpt-5.6-luna` | Parallel, source-local structured extraction |
| Claim trust validation | `gpt-5.6-terra` | Per-claim verification and contradiction handling |
| Screening | `gpt-5.6-terra` | Cross-evidence investment reasoning |
| Memo | `gpt-5.6-terra` | Evidence-backed synthesis |
| Counter-case | `gpt-5.6-terra` | Strong red-team reasoning |
| Truth-gap Judge | `gpt-5.6-terra` | Claim-to-evidence adjudication |
| Verdict brief | `gpt-5.6-luna` | Fast, non-authoritative summarization |

The deterministic fallback remains the default. It lets frontend and backend
integrate without API credentials, while production/demo mode is activated with
`VC_BRAIN_LLM_MODE=openai`.

## Development Notes

- The default integration mode has no third-party runtime dependencies.
- The core functions are in `ai_service/core.py`.
- Bounded public crawling is in `ai_service/crawler.py`.
- Thesis-driven sourcing is in `ai_service/sourcing.py`.
- Persistent Founder Score Memory is in `ai_service/memory.py`; configure a durable location with `VC_BRAIN_MEMORY_PATH` in deployment.
- Founder identity references are intentionally provisional when only a normalized name is available; backend or a reviewer must confirm ambiguous merges.
- The OpenAI model router is in `ai_service/model_router.py`.
- The LangGraph orchestration is in `ai_service/orchestration.py`.
- The HTTP boundary is in `ai_service/server.py`.
- Outputs are deterministic so frontend/backend can mock and integrate reliably.
- The weakest of `Founder`, `Market`, and `Idea vs. Market` is exposed as `weakest_opportunity_axis`; it maps to a functional counter-case focus, not a persona.
- `no previous VC funding` is never inferred from silence: ranking reports only `no_public_evidence` and requires human confirmation.
- `sourcing.run` and the LangGraph deal workflow return audit-safe `audit_events` with stage/model/reference IDs. They never expose model chain-of-thought.
- The local Founder Memory store is an AI-service MVP adapter. Backend owns production persistence, candidate activation/outreach, human decisions, and source-channel outcome feedback.

## Test

```bash
python3 -m unittest discover -s ai_service/tests
```
