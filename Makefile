PYTHON := .venv/bin/python
NPM := npm

.PHONY: dev seed scan eval

dev:
	@set -e; \
	PYTHONPATH=. $(PYTHON) -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 & backend_pid=$$!; \
	trap 'kill $$backend_pid' EXIT INT TERM; \
	cd frontend && $(NPM) run dev -- --hostname 127.0.0.1 --port 3000

seed:
	@PYTHONPATH=. $(PYTHON) -c "from backend.main import store; print(store.seed_cache())"

scan:
	@curl --fail --silent --show-error -X POST http://127.0.0.1:8000/api/scan/run

eval:
	@PYTHONPATH=. $(PYTHON) -m unittest discover -s ai_service/tests
