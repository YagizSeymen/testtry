"""Bounded LangGraph workflow for thesis-driven candidate sourcing."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from . import sourcing

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - dependency-free fallback
    END = START = StateGraph = None


class SourcingWorkflowState(TypedDict, total=False):
    thesis: str
    geography: str
    sector: str
    required_signals: list[str]
    max_candidates: int
    candidate_documents: list[dict[str, Any]]
    sourcing_plan: dict[str, Any]
    discovery: dict[str, Any]
    crawl_enrichment: dict[str, Any]
    founder_profiles: list[dict[str, Any]]
    ranking: dict[str, Any]
    trace: Annotated[list[str], add]


def sourcing_plan_node(state: SourcingWorkflowState) -> SourcingWorkflowState:
    plan = sourcing.endpoint_sourcing_plan(dict(state))
    return {"sourcing_plan": plan, "trace": ["sourcing_plan:luna"]}


def discover_candidates_node(state: SourcingWorkflowState) -> SourcingWorkflowState:
    discovery = sourcing.endpoint_candidates_discover(
        {
            **dict(state),
            "sourcing_plan": state["sourcing_plan"],
        }
    )
    return {"discovery": discovery, "trace": ["candidate_discovery:luna:web_search_or_documents"]}


def crawl_enrichment_node(state: SourcingWorkflowState) -> SourcingWorkflowState:
    if isinstance(state.get("candidate_documents"), list):
        return {"crawl_enrichment": {"mode": "provided_documents"}, "trace": ["crawl_enrichment:provided_documents"]}
    enriched = sourcing.enrich_discovery_with_crawl(state["sourcing_plan"], state["discovery"])
    return {
        "discovery": enriched,
        "crawl_enrichment": {"mode": "cited_source_crawl"},
        "trace": ["crawl_enrichment:parallel_public_pages"],
    }


def founder_memory_node(state: SourcingWorkflowState) -> SourcingWorkflowState:
    profiles = sourcing.update_founder_memory_from_discovery(state["discovery"])
    return {"founder_profiles": profiles, "trace": ["founder_memory:persistent_profile_update"]}


def rank_candidates_node(state: SourcingWorkflowState) -> SourcingWorkflowState:
    ranking = sourcing.endpoint_candidates_rank({"discovery": state["discovery"]})
    return {"ranking": ranking, "trace": ["candidate_rank:deterministic:evidence_gated"]}


def create_sourcing_workflow():
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph is not installed. Run: python3 -m pip install -r ai_service/requirements.txt"
        )
    builder = StateGraph(SourcingWorkflowState)
    builder.add_node("sourcing_plan", sourcing_plan_node)
    builder.add_node("discover_candidates", discover_candidates_node)
    builder.add_node("crawl_enrichment", crawl_enrichment_node)
    builder.add_node("founder_memory", founder_memory_node)
    builder.add_node("rank_candidates", rank_candidates_node)
    builder.add_edge(START, "sourcing_plan")
    builder.add_edge("sourcing_plan", "discover_candidates")
    builder.add_edge("discover_candidates", "crawl_enrichment")
    builder.add_edge("crawl_enrichment", "founder_memory")
    builder.add_edge("founder_memory", "rank_candidates")
    builder.add_edge("rank_candidates", END)
    return builder.compile()


def run_sourcing_workflow(payload: SourcingWorkflowState) -> SourcingWorkflowState:
    if StateGraph is None:
        state: SourcingWorkflowState = dict(payload)
        for node in (
            sourcing_plan_node,
            discover_candidates_node,
            crawl_enrichment_node,
            founder_memory_node,
            rank_candidates_node,
        ):
            update = node(state)
            trace = update.pop("trace", [])
            state.update(update)
            state["trace"] = [*state.get("trace", []), *trace]
        return {**state, "audit_events": sourcing.sourcing_audit_events(state)}
    result = create_sourcing_workflow().invoke(payload)
    return {**result, "audit_events": sourcing.sourcing_audit_events(result)}
