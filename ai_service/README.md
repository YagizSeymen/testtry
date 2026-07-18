# AI Service

Dependency-light implementation of the AI service described by `api-contract.json`.

## Run

```bash
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

## Development Notes

- No third-party runtime dependencies are required.
- The core functions are in `ai_service/core.py`.
- The HTTP boundary is in `ai_service/server.py`.
- Outputs are deterministic so frontend/backend can mock and integrate reliably.
- The `counter_case_lens` is selected from the weakest screening axis. It is not a persona.

## Test

```bash
python3 -m unittest discover -s ai_service/tests
```
