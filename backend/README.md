# Backend (Lane 1)

FastAPI + SQLite Memory for FirstCheck / VentureIntelligence.

Public contract: [`../steps.md`](../steps.md) §3 and [`../api-contract.json`](../api-contract.json).

## Run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Delete local DB if schema changed:
rm -f firstcheck.db
uvicorn app.main:app --reload --port 8000
```

On startup the app creates SQLite tables and seeds from `data/fixtures` if empty.
AI calls go through `IntelligenceService` → `ai_service.pipeline` (deterministic mode by default).

## Implemented so far

**Commit 1 — skeleton**
- Domain: identity + Founder Score
- `POST/GET /api/thesis`, `GET /api/dashboard`, `GET /api/founders/{id}`

**Commit 2 — application pipeline**
- `IntelligenceService` adapter (no LangGraph in routes)
- `POST /api/applications` (extract + founder resolve)
- `GET /api/applications/{id}` (nullable stages + evidence)
- `POST .../screen`, `.../diligence`, `.../memo`
- Stage prerequisites (409) + trust/`based_on` guards + audit rows

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```
