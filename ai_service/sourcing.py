"""Thesis-driven candidate discovery, evidence extraction, and ranking.

This is a bounded sourcing system, not an autonomous investment agent. It
either consumes crawled candidate documents supplied by the backend or, in
OpenAI mode, uses the Responses API web-search tool to locate public leads.
Every candidate assertion is retained only when it names a cited source.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

from . import core, memory
from .crawler import endpoint_research_crawl, source_channel_for
from .model_router import LUNA_MODEL, ModelProviderError, ModelRouter


VALID_SIGNALS = {
    "europe_location",
    "technical_founder",
    "ai_infrastructure",
    "execution",
    "product_traction",
    "public_vc_funding",
    "accelerator",
}

LIVE_DISCOVERY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates", "limitations"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["company_name", "company_url", "founder_names", "observations"],
                "properties": {
                    "company_name": {"type": "string"},
                    "company_url": {"type": ["string", "null"]},
                    "founder_names": {"type": "array", "items": {"type": "string"}},
                    "observations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["signal_type", "claim", "quote", "source_url", "source_title"],
                            "properties": {
                                "signal_type": {"type": "string", "enum": sorted(VALID_SIGNALS)},
                                "claim": {"type": "string"},
                                "quote": {"type": "string"},
                                "source_url": {"type": "string"},
                                "source_title": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}
DEFAULT_REQUIRED_SIGNALS = [
    "europe_location",
    "technical_founder",
    "ai_infrastructure",
    "execution",
    "product_traction",
    "no_previous_vc_funding",
]

SIGNAL_KEYWORDS = {
    "europe_location": [
        "europe",
        "berlin",
        "paris",
        "london",
        "amsterdam",
        "munich",
        "stockholm",
        "helsinki",
        "copenhagen",
        "zurich",
        "lisbon",
        "barcelona",
        "milan",
        "vienna",
        "dublin",
        "european",
    ],
    "technical_founder": [
        "github",
        "open source",
        "engineer",
        "developer",
        "computer science",
        "researcher",
        "cto",
        "technical founder",
        "built",
    ],
    "ai_infrastructure": [
        "ai infrastructure",
        "model serving",
        "inference",
        "vector database",
        "mlops",
        "llmops",
        "compute",
        "gpu",
        "data infrastructure",
        "observability",
        "developer platform",
        "evaluation",
        "agent infrastructure",
    ],
    "execution": [
        "launched",
        "shipped",
        "deployed",
        "released",
        "production",
        "hackathon",
        "winner",
        "finalist",
        "paper",
        "patent",
        "commit",
        "built",
    ],
    "product_traction": [
        "customer",
        "customers",
        "pilot",
        "revenue",
        "arr",
        "users",
        "usage",
        "retention",
        "paying",
        "contract",
        "waitlist",
    ],
    "public_vc_funding": [
        "raised",
        "seed round",
        "series a",
        "venture capital",
        "funding round",
        "backed by",
        "investor",
        "financing",
    ],
    "accelerator": [
        "y combinator",
        "techstars",
        "antler",
        "entrepreneur first",
        "accelerator",
        "fellowship",
    ],
}


def _require_thesis(payload: dict[str, Any]) -> str:
    thesis = str(payload.get("thesis") or "").strip()
    if not thesis:
        raise ValueError("thesis is required.")
    if len(thesis) > 2_000:
        raise ValueError("thesis must not exceed 2,000 characters.")
    return thesis


def _required_signals(payload: dict[str, Any]) -> list[str]:
    supplied = payload.get("required_signals")
    if supplied is None:
        return list(DEFAULT_REQUIRED_SIGNALS)
    if not isinstance(supplied, list):
        raise ValueError("required_signals must be an array when provided.")
    allowed = VALID_SIGNALS | {"no_previous_vc_funding"}
    values = [str(item) for item in supplied if str(item) in allowed]
    return core.dedupe(values) or list(DEFAULT_REQUIRED_SIGNALS)


def _query(query_id: str, query: str, focus: str) -> dict[str, str]:
    return {"query_id": query_id, "query": query, "focus": focus}


def _deterministic_sourcing_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Decompose a natural-language thesis into explicit, reviewable searches."""

    thesis = _require_thesis(payload)
    required = _required_signals(payload)
    geography = str(payload.get("geography") or "Europe").strip()
    sector = str(payload.get("sector") or "AI infrastructure").strip()
    max_candidates = max(1, min(50, int(payload.get("max_candidates") or 20)))
    quoted = f'"{geography}" "{sector}"'
    queries = [
        _query("q_github", f"{quoted} startup founder site:github.com open source", "technical_founder"),
        _query("q_launches", f"{quoted} startup launch product customers pilot", "product_traction"),
        _query("q_hackathons", f"{quoted} founder hackathon winner Devpost MLH", "execution"),
        _query("q_research", f"{quoted} founder arXiv paper patent", "technical_founder"),
        _query("q_accelerators", f"{quoted} startup accelerator cohort", "accelerator"),
        _query("q_funding", f"{quoted} startup funding seed investors", "public_vc_funding"),
    ]
    return {
        "sourcing_run_id": core.stable_id("source_run", thesis, geography, sector),
        "thesis_id": str(payload.get("thesis_id") or "") or None,
        "thesis_version": payload.get("thesis_version") or payload.get("version"),
        "thesis": thesis,
        "required_signals": required,
        "max_candidates": max_candidates,
        "queries": queries,
        "limitations": [
            "No prior VC funding can only be reported as no public funding evidence found; it requires human confirmation.",
            "Sparse public evidence creates a low-confidence cold-start profile, not a negative founder judgment.",
        ],
        "created_at": core.now_iso(),
    }


def _normalise_sourcing_plan(candidate: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Keep live planning flexible without allowing it to mutate the contract."""

    queries = []
    for item in candidate.get("queries", []) if isinstance(candidate.get("queries"), list) else []:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        focus = str(item.get("focus") or "")
        if query and focus in VALID_SIGNALS:
            queries.append(_query(str(item.get("query_id") or core.stable_id("q", query)), query, focus))
    return {
        **fallback,
        "queries": queries or fallback["queries"],
        "limitations": core.dedupe(
            [
                *fallback["limitations"],
                *(str(item) for item in candidate.get("limitations", []) if item),
            ]
        ),
    }


def endpoint_sourcing_plan(payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _deterministic_sourcing_plan(payload)
    if ModelRouter().mode != "openai":
        return fallback
    candidate = ModelRouter().run(
        "sourcing_plan",
        {
            "thesis": fallback["thesis"],
            "required_signals": fallback["required_signals"],
            "seed_query_plan": fallback["queries"],
            "constraints": fallback["limitations"],
        },
        lambda _payload: fallback,
    )
    return _normalise_sourcing_plan(candidate, fallback)


def _candidate_id(candidate: dict[str, Any]) -> str:
    return core.stable_id(
        "candidate",
        candidate.get("company_url") or candidate.get("company_name"),
        ",".join(str(name) for name in candidate.get("founder_names", [])),
    )


def _normalise_candidate(raw: dict[str, Any]) -> dict[str, Any] | None:
    company_name = str(raw.get("company_name") or "").strip()
    if not company_name:
        return None
    founder_names = raw.get("founder_names") if isinstance(raw.get("founder_names"), list) else []
    founder_names = [str(name).strip() for name in founder_names if str(name).strip()]
    aliases_by_name = raw.get("founder_aliases") if isinstance(raw.get("founder_aliases"), dict) else {}
    return {
        "candidate_id": _candidate_id(raw),
        "company_name": company_name,
        "company_url": str(raw.get("company_url") or "").strip() or None,
        "founder_names": founder_names,
        "founder_refs": [
            memory.founder_reference(name, aliases_by_name.get(name) if isinstance(aliases_by_name.get(name), list) else [])
            for name in founder_names
        ],
        "lifecycle_status": "discovered",
        "evidence_ids": [],
        "source_ids": [],
    }


def _signals_for_sentence(sentence: str) -> list[str]:
    lower = sentence.lower()
    signals = [
        signal
        for signal, keywords in SIGNAL_KEYWORDS.items()
        if any(keyword in lower for keyword in keywords)
    ]
    # Keyword matches alone are too weak for a crawler. For example, a GitHub
    # navigation sentence mentioning "users" is not product traction, and a
    # product feature is not evidence that someone is a technical founder.
    if "product_traction" in signals and not re.search(
        r"\b(customer|customers|pilot|revenue|arr|mrr|retention|paying|contract|waitlist)\b", lower
    ):
        signals.remove("product_traction")
    if "europe_location" in signals and not re.search(
        r"\b(berlin|paris|london|amsterdam|munich|stockholm|helsinki|copenhagen|zurich|lisbon|barcelona|milan|vienna|dublin|italy|germany|france|spain|portugal|sweden|finland|denmark|netherlands|switzerland|austria|ireland|bulgaria)\b",
        lower,
    ):
        signals.remove("europe_location")
    if "execution" in signals and not re.search(
        r"\b(launched|shipped|deployed|released|production|hackathon|winner|finalist|paper|patent|commit)\b",
        lower,
    ):
        signals.remove("execution")
    if "technical_founder" in signals and not re.search(
        r"\b(founder|co-founder|ceo|cto|engineer|developer|researcher|maintains)\b", lower
    ):
        signals.remove("technical_founder")
    return signals


def _is_substantive_source_sentence(sentence: str) -> bool:
    """Reject common page chrome before applying evidence keyword rules."""

    lower = sentence.casefold()
    boilerplate = (
        "search code",
        "search repositories",
        "repositories, users, issues",
        "pull requests",
        "sign in",
        "sign up",
        "skip to content",
        "toggle navigation",
        "terms privacy",
        "cookie preferences",
    )
    return len(core.tokenize(sentence)) >= 6 and not any(fragment in lower for fragment in boilerplate)


def _source_from_document(source: dict[str, Any]) -> dict[str, Any]:
    url = str(source.get("url") or "").strip()
    title = str(source.get("title") or urlparse(url).hostname or url)
    kind = str(source.get("kind") or "other")
    return {
        "source_id": str(source.get("source_id") or core.stable_id("src", url, title)),
        "url": url,
        "canonical_url": str(source.get("canonical_url") or url) or None,
        "title": title,
        "kind": kind,
        "channel": str(source.get("channel") or source_channel_for(kind)),
        "content_hash": source.get("content_hash"),
        "published_at": source.get("published_at"),
        "raw_document_id": source.get("raw_document_id"),
        "fetched_at": str(source.get("fetched_at") or core.now_iso()),
        "http_status": source.get("http_status"),
    }


def _evidence_record(
    candidate: dict[str, Any], source: dict[str, Any], signal: str, sentence: str
) -> dict[str, Any]:
    claim = sentence.strip()
    trust_score, trust_status = core.trust_for(source, claim)
    return {
        "evidence_id": core.stable_id("cev", candidate["candidate_id"], source["source_id"], signal, claim),
        "candidate_id": candidate["candidate_id"],
        "source_id": source["source_id"],
        "source_url": source["url"],
        "source_title": source["title"],
        "signal_type": signal,
        "claim": claim,
        "quote": claim,
        "confidence": "high" if source["kind"] in {"github", "paper", "patent", "hackathon", "accelerator"} else "medium",
        "trust_score": trust_score,
        "trust_status": trust_status,
        "contradicted_by_evidence_ids": [],
        "published_at": source.get("published_at"),
        "captured_at": core.now_iso(),
    }


def _discover_from_documents(plan: dict[str, Any], documents: list[Any]) -> dict[str, Any]:
    candidates: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        candidate = _normalise_candidate(document.get("candidate") if isinstance(document.get("candidate"), dict) else {})
        source_input = document.get("source") if isinstance(document.get("source"), dict) else {}
        page_text = str(document.get("page_text") or "")
        if candidate is None or not source_input.get("url") or not page_text:
            continue
        source = _source_from_document(source_input)
        candidates[candidate["candidate_id"]] = candidates.get(candidate["candidate_id"], candidate)
        sources[source["source_id"]] = source
        for sentence in core.split_sentences(page_text)[:80]:
            if not _is_substantive_source_sentence(sentence):
                continue
            for signal in _signals_for_sentence(sentence):
                item = _evidence_record(candidates[candidate["candidate_id"]], source, signal, sentence)
                evidence[item["evidence_id"]] = item

    for item in evidence.values():
        candidate = candidates[item["candidate_id"]]
        candidate["evidence_ids"] = core.dedupe([*candidate["evidence_ids"], item["evidence_id"]])
        candidate["source_ids"] = core.dedupe([*candidate["source_ids"], item["source_id"]])
    return {
        "sourcing_run_id": plan["sourcing_run_id"],
        "thesis_id": plan.get("thesis_id"),
        "thesis_version": plan.get("thesis_version"),
        "thesis": plan["thesis"],
        "query_plan": plan["queries"],
        "required_signals": plan["required_signals"],
        "candidates": list(candidates.values()),
        "sources": list(sources.values()),
        "evidence": list(evidence.values()),
        "limitations": [
            *plan["limitations"],
            "Deterministic mode only ranks the supplied crawled candidate documents; it does not make a web-search request.",
        ],
        "created_at": core.now_iso(),
    }


def _attr(value: Any, key: str, default: Any = None) -> Any:
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def _response_citation_urls(response: Any) -> set[str]:
    urls: set[str] = set()
    for item in _attr(response, "output", []) or []:
        # `include=["web_search_call.action.sources"]` returns every source
        # the tool consulted. This is more reliable than inline annotations
        # when the model's final answer is constrained to JSON.
        action = _attr(item, "action", {})
        for source in _attr(action, "sources", []) or []:
            url = _attr(source, "url") or _attr(source, "source_url")
            if url:
                urls.add(str(url))
        for content in _attr(item, "content", []) or []:
            for annotation in _attr(content, "annotations", []) or []:
                citation = _attr(annotation, "url_citation", {})
                url = _attr(annotation, "url") or _attr(citation, "url")
                if url:
                    urls.add(str(url))
    return urls


def _parse_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.S)
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ModelProviderError("Web discovery returned a non-object JSON value.")
    return parsed


def _discover_with_openai_web_search(plan: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ModelProviderError("OPENAI_API_KEY is required for live web candidate discovery.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ModelProviderError("Install ai_service/requirements.txt to enable web discovery.") from exc

    prompt = {
        "thesis": plan["thesis"],
        "queries": plan["queries"],
        "max_candidates": plan["max_candidates"],
        "output_contract": {
            "candidates": [
                {
                    "company_name": "string",
                    "company_url": "string or null",
                    "founder_names": ["string"],
                    "observations": [
                        {
                            "signal_type": "one allowed signal",
                            "claim": "short source-backed fact",
                            "quote": "short source-derived excerpt or accurate qualified summary",
                            "source_url": "must exactly equal a web citation URL",
                        }
                    ],
                }
            ],
            "limitations": ["string"],
        },
    }
    developer = (
        "You are the bounded outbound-sourcing stage for a venture fund. Search the web to find "
        "candidate founders and companies matching the thesis. Do not recommend investments or invent facts. "
        "Do not return a company when you find public VC funding evidence for it; prefer companies for which the "
        "searched public corpus has no disclosed funding evidence, while stating that this remains uncertain and "
        "requires human confirmation. Return JSON only. Keep a candidate observation only when its source_url "
        "matches a URL citation provided by web search. Report funding as public_vc_funding only when public evidence exists."
    )
    response = OpenAI(api_key=api_key).responses.create(
        model=LUNA_MODEL,
        tools=[{"type": "web_search", "search_context_size": "medium"}],
        include=["web_search_call.action.sources"],
        text={
            "format": {
                "type": "json_schema",
                "name": "vc_brain_web_discovery",
                "strict": True,
                "schema": LIVE_DISCOVERY_SCHEMA,
            }
        },
        input=[
            {"role": "developer", "content": developer},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    parsed = _parse_json_object(str(_attr(response, "output_text", "")))
    citation_urls = _response_citation_urls(response)
    if not citation_urls:
        raise ModelProviderError("Web discovery returned no URL citations; candidate claims cannot be retained.")

    candidates: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for raw_candidate in parsed.get("candidates", []):
        candidate = _normalise_candidate(raw_candidate if isinstance(raw_candidate, dict) else {})
        if candidate is None:
            continue
        candidates[candidate["candidate_id"]] = candidate
        for observation in raw_candidate.get("observations", []):
            if not isinstance(observation, dict):
                continue
            source_url = str(observation.get("source_url") or "")
            signal = str(observation.get("signal_type") or "")
            if source_url not in citation_urls or signal not in VALID_SIGNALS:
                continue
            source = _source_from_document(
                {
                    "url": source_url,
                    "title": str(observation.get("source_title") or urlparse(source_url).hostname or source_url),
                    "kind": "other",
                    "channel": "web_search",
                }
            )
            sources[source["source_id"]] = source
            claim = str(observation.get("claim") or "").strip()
            quote = str(observation.get("quote") or claim).strip()
            if not claim or not quote:
                continue
            item = {
                **_evidence_record(candidate, source, signal, claim),
                "quote": quote,
            }
            evidence[item["evidence_id"]] = item
            candidate["evidence_ids"] = core.dedupe([*candidate["evidence_ids"], item["evidence_id"]])
            candidate["source_ids"] = core.dedupe([*candidate["source_ids"], source["source_id"]])
    result = {
        "sourcing_run_id": plan["sourcing_run_id"],
        "thesis_id": plan.get("thesis_id"),
        "thesis_version": plan.get("thesis_version"),
        "thesis": plan["thesis"],
        "query_plan": plan["queries"],
        "required_signals": plan["required_signals"],
        "candidates": [item for item in candidates.values() if item["evidence_ids"]],
        "sources": list(sources.values()),
        "evidence": list(evidence.values()),
        "limitations": list(plan["limitations"]),
        "created_at": core.now_iso(),
    }
    result["limitations"] = [
        *result["limitations"],
        *(str(item) for item in parsed.get("limitations", []) if item),
        "Live discovery retains only observations tied to returned web-search citations. Crawl retained source URLs before final diligence.",
    ]
    return result


def endpoint_candidates_discover(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("sourcing_plan") if isinstance(payload.get("sourcing_plan"), dict) else endpoint_sourcing_plan(payload)
    documents = payload.get("candidate_documents")
    if isinstance(documents, list):
        return _discover_from_documents(plan, documents)
    if ModelRouter().mode == "openai":
        return _discover_with_openai_web_search(plan)
    raise ValueError(
        "candidate_documents are required in deterministic mode. Set VC_BRAIN_LLM_MODE=openai for live web discovery."
    )


def _funding_coverage(discovery: dict[str, Any]) -> bool:
    query_plan = discovery.get("query_plan") if isinstance(discovery.get("query_plan"), list) else []
    return any(isinstance(query, dict) and query.get("focus") == "public_vc_funding" for query in query_plan)


def endpoint_candidates_rank(payload: dict[str, Any]) -> dict[str, Any]:
    discovery = payload.get("discovery")
    if not isinstance(discovery, dict):
        raise ValueError("discovery must be a CandidateDiscoveryResult object.")
    required = discovery.get("required_signals") if isinstance(discovery.get("required_signals"), list) else DEFAULT_REQUIRED_SIGNALS
    evidence = discovery.get("evidence") if isinstance(discovery.get("evidence"), list) else []
    evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        if isinstance(item, dict) and item.get("candidate_id"):
            evidence_by_candidate.setdefault(str(item["candidate_id"]), []).append(item)
    funding_coverage = _funding_coverage(discovery)
    ranked = []
    for candidate in discovery.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        candidate_evidence = evidence_by_candidate.get(str(candidate.get("candidate_id")), [])
        evidence_ids_by_signal: dict[str, list[str]] = {}
        for item in candidate_evidence:
            signal = str(item.get("signal_type") or "")
            evidence_ids_by_signal.setdefault(signal, []).append(str(item.get("evidence_id")))
        eligibility = []
        score = 0
        hard_exclusion = False
        for signal in required:
            if signal == "no_previous_vc_funding":
                funding_ids = evidence_ids_by_signal.get("public_vc_funding", [])
                if funding_ids:
                    eligibility.append(
                        {
                            "criterion": signal,
                            "status": "public_vc_funding_found",
                            "evidence_ids": funding_ids,
                            "note": "Public funding evidence was found; this conflicts with the thesis filter.",
                        }
                    )
                    score -= 35
                    hard_exclusion = True
                elif funding_coverage:
                    eligibility.append(
                        {
                            "criterion": signal,
                            "status": "no_public_evidence",
                            "evidence_ids": [],
                            "note": "No public VC funding evidence was found in the searched corpus. Human confirmation is required.",
                        }
                    )
                    score += 5
                else:
                    eligibility.append(
                        {
                            "criterion": signal,
                            "status": "insufficient_coverage",
                            "evidence_ids": [],
                            "note": "Funding coverage is insufficient; do not infer a no-funding conclusion.",
                        }
                    )
                    score -= 5
                continue
            ids = evidence_ids_by_signal.get(signal, [])
            eligibility.append(
                {
                    "criterion": signal,
                    "status": "supported" if ids else "missing",
                    "evidence_ids": ids,
                    "note": "Source-backed signal found." if ids else "No source-backed signal found in the current corpus.",
                }
            )
            score += 18 if ids else -5
        required_supported = sum(1 for item in eligibility if item["status"] == "supported")
        status = "excluded" if hard_exclusion else "candidate" if required_supported >= 4 else "needs_review"
        ranked.append(
            {
                **candidate,
                "fit_score": max(0, min(100, score + 40)),
                "status": status,
                "manual_review_required": True,
                "eligibility": eligibility,
            }
        )
    ranked.sort(key=lambda item: (-int(item["fit_score"]), item["company_name"].lower()))
    for index, candidate in enumerate(ranked, start=1):
        candidate["rank"] = index
    return {
        "sourcing_run_id": str(discovery.get("sourcing_run_id") or ""),
        "thesis_id": discovery.get("thesis_id"),
        "thesis_version": discovery.get("thesis_version"),
        "thesis": str(discovery.get("thesis") or ""),
        "ranked_candidates": ranked,
        "limitations": [
            *(discovery.get("limitations") if isinstance(discovery.get("limitations"), list) else []),
            "Ranking prioritizes evidence coverage and thesis fit. It is not an investment decision.",
        ],
        "created_at": core.now_iso(),
    }


def enrich_discovery_with_crawl(plan: dict[str, Any], discovery: dict[str, Any]) -> dict[str, Any]:
    """Fetch cited lead sources and add source-page evidence before ranking.

    This is intentionally best-effort: a robots refusal or inaccessible page is
    recorded as a limitation, while the original citation remains visible.
    """

    sources = discovery.get("sources") if isinstance(discovery.get("sources"), list) else []
    source_by_id = {str(item.get("source_id")): item for item in sources if isinstance(item, dict) and item.get("source_id")}
    urls = core.dedupe([str(item.get("url")) for item in sources if isinstance(item, dict) and item.get("url")])[:12]
    if not urls:
        return discovery
    crawl = endpoint_research_crawl({"urls": urls})
    crawled_by_url = {
        str(document["source"].get("url")): document
        for document in crawl["documents"]
        if isinstance(document, dict) and isinstance(document.get("source"), dict)
    }
    candidate_documents = []
    for candidate in discovery.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        for source_id in candidate.get("source_ids", []):
            source = source_by_id.get(str(source_id))
            if not source:
                continue
            crawled = crawled_by_url.get(str(source.get("url")))
            if crawled:
                candidate_documents.append({"candidate": candidate, **crawled})
    if not candidate_documents:
        return {
            **discovery,
            "limitations": [
                *(discovery.get("limitations") if isinstance(discovery.get("limitations"), list) else []),
                *(f"Crawler: {item['url']}: {item['reason']}" for item in crawl["failures"]),
            ],
        }

    enriched = _discover_from_documents(plan, candidate_documents)
    candidates: dict[str, dict[str, Any]] = {
        str(item.get("candidate_id")): dict(item)
        for item in discovery.get("candidates", [])
        if isinstance(item, dict) and item.get("candidate_id")
    }
    for item in enriched["candidates"]:
        current = candidates.setdefault(str(item["candidate_id"]), dict(item))
        current["evidence_ids"] = core.dedupe([*current.get("evidence_ids", []), *item.get("evidence_ids", [])])
        current["source_ids"] = core.dedupe([*current.get("source_ids", []), *item.get("source_ids", [])])
    source_map = {str(item.get("source_id")): item for item in sources if isinstance(item, dict) and item.get("source_id")}
    source_map.update({str(item.get("source_id")): item for item in enriched["sources"] if item.get("source_id")})

    def exact_crawl_support(item: dict[str, Any]) -> bool:
        document = crawled_by_url.get(str(item.get("source_url") or ""))
        if document is None:
            # A citation that could not be crawled remains source-linked but is
            # visibly subject to human review through the normal limitations.
            return True
        page = re.sub(r"\s+", " ", str(document.get("page_text") or "")).casefold()
        quote = re.sub(r"\s+", " ", str(item.get("quote") or item.get("claim") or "")).strip().casefold()
        return len(quote) >= 25 and quote in page

    evidence_map = {
        str(item.get("evidence_id")): item
        for item in discovery.get("evidence", [])
        if isinstance(item, dict) and item.get("evidence_id") and exact_crawl_support(item)
    }
    evidence_map.update({str(item.get("evidence_id")): item for item in enriched["evidence"] if item.get("evidence_id")})
    for candidate in candidates.values():
        candidate["evidence_ids"] = []
        candidate["source_ids"] = []
    for item in evidence_map.values():
        candidate = candidates.get(str(item.get("candidate_id") or ""))
        if candidate is None:
            continue
        candidate["evidence_ids"] = core.dedupe([*candidate["evidence_ids"], str(item["evidence_id"])])
        candidate["source_ids"] = core.dedupe([*candidate["source_ids"], str(item["source_id"])])
    return {
        **discovery,
        "candidates": list(candidates.values()),
        "sources": list(source_map.values()),
        "evidence": list(evidence_map.values()),
        "limitations": [
            *(discovery.get("limitations") if isinstance(discovery.get("limitations"), list) else []),
            *(f"Crawler: {item['url']}: {item['reason']}" for item in crawl["failures"]),
        ],
    }


def update_founder_memory_from_discovery(discovery: dict[str, Any]) -> list[dict[str, Any]]:
    """Persist public founder milestones before the founder applies to the fund."""

    evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for item in discovery.get("evidence", []):
        if isinstance(item, dict) and item.get("candidate_id"):
            evidence_by_candidate.setdefault(str(item["candidate_id"]), []).append(item)
    profiles = []
    for candidate in discovery.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        candidate_evidence = evidence_by_candidate.get(str(candidate.get("candidate_id")), [])
        for founder_name in candidate.get("founder_names", []):
            if str(founder_name).strip():
                profiles.append(
                    memory.endpoint_founder_memory_upsert(
                        {"founder_name": str(founder_name), "evidence": candidate_evidence}
                    )
                )
    return profiles


def sourcing_audit_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return reviewer-visible orchestration metadata, never model reasoning."""

    plan = result.get("sourcing_plan") if isinstance(result.get("sourcing_plan"), dict) else {}
    discovery = result.get("discovery") if isinstance(result.get("discovery"), dict) else {}
    ranking = result.get("ranking") if isinstance(result.get("ranking"), dict) else {}
    run_id = str(plan.get("sourcing_run_id") or discovery.get("sourcing_run_id") or ranking.get("sourcing_run_id") or "")
    thesis_id = str(plan.get("thesis_id") or "")
    candidates = discovery.get("candidates") if isinstance(discovery.get("candidates"), list) else []
    sources = discovery.get("sources") if isinstance(discovery.get("sources"), list) else []
    profiles = result.get("founder_profiles") if isinstance(result.get("founder_profiles"), list) else []
    return [
        core.audit_trace_event(
            stage="sourcing.plan",
            run_id=run_id,
            model=LUNA_MODEL,
            input_reference_ids=[thesis_id],
            output_reference_ids=[run_id],
            status_detail="Generated a bounded, reviewable sourcing query plan.",
        ),
        core.audit_trace_event(
            stage="sourcing.discover",
            run_id=run_id,
            model=LUNA_MODEL,
            input_reference_ids=[run_id],
            output_reference_ids=[str(item.get("candidate_id")) for item in candidates if isinstance(item, dict)],
            status_detail="Retained only source-backed candidate observations.",
        ),
        core.audit_trace_event(
            stage="research.crawl",
            run_id=run_id,
            input_reference_ids=[str(item.get("source_id")) for item in sources if isinstance(item, dict)],
            output_reference_ids=[str(item.get("source_id")) for item in sources if isinstance(item, dict)],
            status_detail="Crawl enrichment is bounded to cited public sources when it runs.",
        ),
        core.audit_trace_event(
            stage="founders.memory.upsert",
            run_id=run_id,
            input_reference_ids=[str(item.get("candidate_id")) for item in candidates if isinstance(item, dict)],
            output_reference_ids=[str(item.get("founder_id")) for item in profiles if isinstance(item, dict)],
            status_detail="Updated evidence-backed Founder Memory profiles.",
        ),
        core.audit_trace_event(
            stage="sourcing.rank",
            run_id=run_id,
            input_reference_ids=[str(item.get("candidate_id")) for item in candidates if isinstance(item, dict)],
            output_reference_ids=[str(item.get("candidate_id")) for item in ranking.get("ranked_candidates", []) if isinstance(item, dict)],
            status_detail="Ranked evidence coverage and thesis fit; no investment decision was made.",
        ),
    ]


def run_sourcing_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    plan = endpoint_sourcing_plan(payload)
    discovery = endpoint_candidates_discover({**payload, "sourcing_plan": plan})
    if not isinstance(payload.get("candidate_documents"), list):
        discovery = enrich_discovery_with_crawl(plan, discovery)
    founder_profiles = update_founder_memory_from_discovery(discovery)
    ranking = endpoint_candidates_rank({"discovery": discovery})
    result = {
        "sourcing_plan": plan,
        "discovery": discovery,
        "ranking": ranking,
        "founder_profiles": founder_profiles,
    }
    return {**result, "audit_events": sourcing_audit_events(result)}
