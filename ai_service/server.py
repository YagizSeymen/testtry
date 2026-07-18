"""HTTP server for the AI service.

Run:
    python3 -m ai_service.server --port 8001
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from . import crawler, memory, pipeline, runtime, sourcing, sourcing_orchestration
from .model_router import ModelRouter, model_manifest


HandlerFn = Callable[[dict[str, Any]], dict[str, Any]]


ROUTES: dict[str, HandlerFn] = {
    # Contract v1 internal AI boundary. Backend owns all /api product routes
    # and may call these fixed stages over HTTP or import ai_service.pipeline.
    "/v1/ai/extract": pipeline.endpoint_extract,
    "/v1/ai/query": pipeline.endpoint_query,
    "/v1/ai/screen": pipeline.endpoint_screen,
    "/v1/ai/diligence": pipeline.endpoint_diligence,
    "/v1/ai/memo": pipeline.endpoint_memo,
    "/v1/ai/adversary": pipeline.endpoint_adversary,
    "/v1/ai/adversary/verify": pipeline.endpoint_verify_adversary,
    "/v1/ai/application/run": pipeline.endpoint_application_run,
    # Legacy helpers are kept during backend migration. They are not part of
    # api-contract.json and must not be wired into the public product API.
    "/v1/ai/sourcing/plan": sourcing.endpoint_sourcing_plan,
    "/v1/ai/sourcing/discover": sourcing.endpoint_candidates_discover,
    "/v1/ai/sourcing/rank": sourcing.endpoint_candidates_rank,
    "/v1/ai/sourcing/run": sourcing_orchestration.run_sourcing_workflow,
    "/v1/ai/research/crawl": crawler.endpoint_research_crawl,
    "/v1/ai/founders/memory/upsert": memory.endpoint_founder_memory_upsert,
    "/v1/ai/founders/memory/get": memory.endpoint_founder_memory_get,
    "/v1/ai/founders/memory/resolve": memory.endpoint_founder_memory_resolve,
    "/v1/ai/research/plan": runtime.endpoint_research_plan,
    "/v1/ai/evidence/extract": runtime.endpoint_evidence_extract,
    "/v1/ai/evidence/verify": runtime.endpoint_evidence_verify,
    "/v1/ai/screen/score": runtime.endpoint_screen_score,
    "/v1/ai/memo/write": runtime.endpoint_memo_write,
    "/v1/ai/adversary/write": runtime.endpoint_adversary_write,
    "/v1/ai/truth-gap/verify": runtime.endpoint_truth_gap_verify,
    "/v1/ai/verdict/brief": runtime.endpoint_verdict_brief,
}


class AIServiceHandler(BaseHTTPRequestHandler):
    server_version = "VCBrainAIService/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/health", "/v1/ai/health"}:
            self.write_json(
                200,
                {
                    "status": "ok",
                    "service": "vc-brain-ai",
                    "runtime_mode": ModelRouter().mode,
                    "model_by_stage": model_manifest(),
                },
            )
            return
        self.write_json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        handler = ROUTES.get(path)
        if handler is None:
            self.write_json(404, {"error": "not_found", "path": path})
            return

        try:
            payload = self.read_json()
            result = handler(payload)
        except ValueError as exc:
            self.write_json(400, {"error": "bad_request", "message": str(exc)})
            return
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self.write_json(500, {"error": "internal_error", "message": str(exc)})
            return

        self.write_json(200, result)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[ai-service] {self.address_string()} - {fmt % args}")


def create_server(host: str = "127.0.0.1", port: int = 8001) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), AIServiceHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run The VC Brain AI service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    host, port = server.server_address
    print(f"AI service listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down AI service")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
