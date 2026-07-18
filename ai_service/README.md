# AI Service

AI service implementation for the bounded workflow described by `api-contract.json`.

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

- `POST /research/plan`
- `POST /evidence/extract`
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
research plan [Luna]
  -> evidence extraction per source [Luna, parallel]
  -> Memory merge [barrier]
  -> screening [Terra]
  -> memo [Terra]
  -> one counter-case [Terra]
  -> truth-gap Judge [Terra]
  -> optional verdict brief [Luna]
  -> human decision outside the graph
```

`ai_service/orchestration.py` implements this graph. The only fan-out is source
extraction, because documents are independent. Screening and all later stages
are sequential because they require the merged, verified state from the prior
stage.

## Model Routing

| Stage | Model | Reason |
| --- | --- | --- |
| Research plan | `gpt-5.6-luna` | High-volume query planning |
| Evidence extraction | `gpt-5.6-luna` | Parallel, source-local structured extraction |
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
- The OpenAI model router is in `ai_service/model_router.py`.
- The LangGraph orchestration is in `ai_service/orchestration.py`.
- The HTTP boundary is in `ai_service/server.py`.
- Outputs are deterministic so frontend/backend can mock and integrate reliably.
- The `counter_case_lens` is selected from the weakest screening axis. It is not a persona.

## Test

```bash
python3 -m unittest discover -s ai_service/tests
```
