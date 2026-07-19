# Backend (Lane 1)

FastAPI + SQLite Memory for FirstCheck / VentureIntelligence.

Public contract: [`../steps.md`](../steps.md) §3 and [`../api-contract.json`](../api-contract.json).

## Run

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000
```

On startup the app creates SQLite tables and seeds from `data/fixtures` if empty.

## This commit (P0 skeleton)

- Domain: name identity + Founder Score formula
- Persistence: SQLite models
- APIs: `POST/GET /api/thesis`, `GET /api/dashboard`, `GET /api/founders/{id}`
- Seed: Maya Chen synthetic founder from fixtures

## Tests

```bash
cd backend
python3 -m pytest -q
```
