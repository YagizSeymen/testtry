"""Founder Memory retrieval and grounded chat generation.

The product database owns chunk persistence. This module owns the bounded AI
operations: embedding, similarity ranking, and one cited answer. It never
crawls the web and it never treats retrieved Memory as instructions.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .model_router import ModelProviderError, ModelRouter, configured_openai_api_key, exception_type_chain


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "founder_chat.md"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 256
MAX_RETRIEVED_CHUNKS = 8

CHAT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_chunk_ids": {"type": "array", "items": {"type": "string"}},
        "insufficient_evidence": {"type": "boolean"},
    },
    "required": ["answer", "cited_chunk_ids", "insufficient_evidence"],
    "additionalProperties": False,
}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 1}


def _lexical_score(query: str, chunk: dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    corpus = f"{chunk.get('founder_name', '')} {chunk.get('label', '')} {chunk.get('content', '')}"
    corpus_tokens = _tokens(corpus)
    overlap = len(query_tokens & corpus_tokens) / len(query_tokens)
    phrase_bonus = 0.2 if query.casefold().strip() in corpus.casefold() else 0.0
    return overlap + phrase_bonus


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _parse_embedding(value: Any) -> list[float] | None:
    if isinstance(value, list) and value and all(isinstance(item, (int, float)) for item in value):
        return [float(item) for item in value]
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return _parse_embedding(parsed)


def _deterministic_answer(message: str, ranked: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [chunk for chunk in ranked if float(chunk.get("retrieval_score", 0)) > 0][:3]
    if not selected:
        return {
            "answer": "I could not find relevant support for that question in the stored Founder Memory.",
            "cited_chunk_ids": [],
            "insufficient_evidence": True,
            "embedding_updates": {},
            "retrieved_chunk_ids": [],
        }
    statements = []
    for index, chunk in enumerate(selected, start=1):
        excerpt = re.sub(r"\s+", " ", str(chunk["content"])).strip()[:320]
        statements.append(f"{chunk['founder_name']}: {excerpt} [{index}]")
    return {
        "answer": "Based only on stored Founder Memory, " + " ".join(statements),
        "cited_chunk_ids": [str(chunk["chunk_id"]) for chunk in selected],
        "insufficient_evidence": False,
        "embedding_updates": {},
        "retrieved_chunk_ids": [str(chunk["chunk_id"]) for chunk in selected],
    }


def answer_founder_memory(payload: dict[str, Any]) -> dict[str, Any]:
    """Retrieve relevant Memory chunks and return one grounded cited answer."""

    message = str(payload.get("message") or "").strip()
    chunks = [dict(chunk) for chunk in payload.get("chunks", []) if isinstance(chunk, dict)]
    router = ModelRouter()
    invocation = router.invocation("founder_chat")

    if invocation.mode == "deterministic":
        ranked = sorted(
            ({**chunk, "retrieval_score": _lexical_score(message, chunk)} for chunk in chunks),
            key=lambda chunk: float(chunk["retrieval_score"]),
            reverse=True,
        )
        return _deterministic_answer(message, ranked)
    if invocation.mode != "openai":
        raise ModelProviderError("VC_BRAIN_LLM_MODE must be 'deterministic' or 'openai'.")

    api_key = configured_openai_api_key()
    if not api_key:
        raise ModelProviderError("OPENAI_API_KEY is required when VC_BRAIN_LLM_MODE=openai.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ModelProviderError("Install ai_service/requirements.txt to enable Founder Memory chat.") from exc

    # Embedding and generation share one 60-second serverless request. Bound
    # each provider round trip so a stalled call cannot consume the full slot.
    client = OpenAI(api_key=api_key, timeout=25.0, max_retries=0)
    missing = [chunk for chunk in chunks if _parse_embedding(chunk.get("embedding_json")) is None]
    embedding_inputs = [message] + [str(chunk["content"]) for chunk in missing]
    try:
        embedding_response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=embedding_inputs,
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )
    except Exception as exc:
        raise ModelProviderError(
            f"OpenAI embedding request failed for founder_chat: {exc} [{exception_type_chain(exc)}]"
        ) from exc

    vectors = [list(item.embedding) for item in embedding_response.data]
    query_embedding = vectors[0]
    embedding_updates: dict[str, list[float]] = {}
    for chunk, embedding in zip(missing, vectors[1:]):
        chunk["embedding_json"] = embedding
        embedding_updates[str(chunk["chunk_id"])] = embedding

    ranked: list[dict[str, Any]] = []
    for chunk in chunks:
        embedding = _parse_embedding(chunk.get("embedding_json"))
        vector_score = _cosine(query_embedding, embedding or [])
        score = vector_score + min(0.12, _lexical_score(message, chunk) * 0.1)
        ranked.append({**chunk, "retrieval_score": score})
    ranked.sort(key=lambda chunk: float(chunk["retrieval_score"]), reverse=True)
    selected = ranked[:MAX_RETRIEVED_CHUNKS]

    context = [
        {
            "citation": index,
            "chunk_id": chunk["chunk_id"],
            "founder": chunk["founder_name"],
            "source_type": chunk["source_type"],
            "label": chunk["label"],
            "url": chunk.get("url"),
            "content": chunk["content"],
        }
        for index, chunk in enumerate(selected, start=1)
    ]
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    request = {
        "model": invocation.model,
        "reasoning": {"effort": "none"},
        "input": [
            {"role": "developer", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": message, "recent_conversation": history[-8:], "retrieved_memory": context},
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "founder_memory_answer",
                "strict": True,
                "schema": CHAT_RESPONSE_SCHEMA,
            }
        },
    }
    try:
        response = client.responses.create(**request)
        result = json.loads(response.output_text)
    except Exception as exc:
        raise ModelProviderError(
            f"OpenAI request failed for founder_chat: {exc} [{exception_type_chain(exc)}]"
        ) from exc
    if not isinstance(result, dict):
        raise ModelProviderError("Founder Memory chat returned a non-object JSON value.")

    allowed_ids = {str(chunk["chunk_id"]) for chunk in selected}
    cited_ids = list(
        dict.fromkeys(
            str(chunk_id) for chunk_id in result.get("cited_chunk_ids", []) if str(chunk_id) in allowed_ids
        )
    )
    return {
        "answer": str(result.get("answer") or "I could not produce a grounded answer."),
        "cited_chunk_ids": cited_ids,
        "insufficient_evidence": bool(result.get("insufficient_evidence")) or not cited_ids,
        "embedding_updates": embedding_updates,
        "retrieved_chunk_ids": [str(chunk["chunk_id"]) for chunk in selected],
    }
