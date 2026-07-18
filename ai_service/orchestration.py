"""Bounded LangGraph orchestration for The VC Brain.

The graph is intentionally a fixed DAG:
research plan -> parallel evidence extraction -> screening -> memo -> counter-case
-> truth-gap verification -> optional brief -> human review outside the graph.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from . import runtime

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send
except ImportError:  # pragma: no cover - exercised only without optional dependency
    END = START = Send = StateGraph = None


class WorkflowState(TypedDict, total=False):
    deal: dict[str, Any]
    documents: list[dict[str, Any]]
    include_verdict_brief: bool
    research_plan: dict[str, Any]
    evidence_batches: Annotated[list[list[dict[str, Any]]], add]
    evidence: list[dict[str, Any]]
    screening: dict[str, Any]
    memo: dict[str, Any]
    adversary_report: dict[str, Any]
    truth_gap_verification: dict[str, Any]
    verdict_brief: dict[str, Any]
    trace: Annotated[list[str], add]


def research_plan_node(state: WorkflowState) -> WorkflowState:
    return {
        "research_plan": runtime.endpoint_research_plan({"deal": state["deal"]}),
        "trace": ["research_plan:luna"],
    }


def fan_out_evidence(state: WorkflowState) -> list[Any] | Literal["evidence_merge"]:
    """Map independent source documents to LangGraph tasks, then join at Memory."""

    documents = state.get("documents", [])
    if not documents:
        return "evidence_merge"
    return [
        Send("extract_document", {"deal": state["deal"], "document": document})
        for document in documents
    ]


def extract_document_node(state: WorkflowState) -> WorkflowState:
    document = state["document"]
    result = runtime.endpoint_evidence_extract(
        {
            "deal": state["deal"],
            "source": document["source"],
            "page_text": document["page_text"],
        }
    )
    return {
        "evidence_batches": [result["evidence"]],
        "trace": ["evidence_extract:luna"],
    }


def evidence_merge_node(state: WorkflowState) -> WorkflowState:
    batches = state.get("evidence_batches", [])
    evidence = [item for batch in batches for item in batch]
    evidence.sort(key=lambda item: str(item.get("evidence_id", "")))
    return {
        "evidence": evidence,
        "trace": [f"evidence_merge:barrier:parallel_sources={len(batches)}"],
    }


def screening_node(state: WorkflowState) -> WorkflowState:
    return {
        "screening": runtime.endpoint_screen_score(
            {"deal": state["deal"], "evidence": state.get("evidence", [])}
        ),
        "trace": ["screen_score:terra"],
    }


def memo_node(state: WorkflowState) -> WorkflowState:
    return {
        "memo": runtime.endpoint_memo_write(
            {
                "deal": state["deal"],
                "evidence": state.get("evidence", []),
                "screening": state["screening"],
            }
        ),
        "trace": ["memo_write:terra"],
    }


def counter_case_node(state: WorkflowState) -> WorkflowState:
    return {
        "adversary_report": runtime.endpoint_adversary_write(
            {
                "deal": state["deal"],
                "evidence": state.get("evidence", []),
                "screening": state["screening"],
                "memo": state["memo"],
            }
        ),
        "trace": ["counter_case:terra:single_pass"],
    }


def truth_gap_node(state: WorkflowState) -> WorkflowState:
    return {
        "truth_gap_verification": runtime.endpoint_truth_gap_verify(
            {
                "deal": state["deal"],
                "evidence": state.get("evidence", []),
                "memo": state["memo"],
                "adversary_report": state["adversary_report"],
            }
        ),
        "trace": ["truth_gap_verify:terra"],
    }


def verdict_brief_node(state: WorkflowState) -> WorkflowState:
    return {
        "verdict_brief": runtime.endpoint_verdict_brief(
            {
                "deal": state["deal"],
                "evidence": state.get("evidence", []),
                "screening": state["screening"],
                "memo": state["memo"],
                "adversary_report": state["adversary_report"],
                "truth_gap_verification": state["truth_gap_verification"],
            }
        ),
        "trace": ["verdict_brief:luna:non_authoritative"],
    }


def after_truth_gap(state: WorkflowState) -> Literal["brief", "end"]:
    return "brief" if state.get("include_verdict_brief", False) else "end"


def create_workflow():
    """Create the fixed workflow graph; human approval is deliberately outside it."""

    if StateGraph is None:
        raise RuntimeError(
            "LangGraph is not installed. Run: python3 -m pip install -r ai_service/requirements.txt"
        )
    builder = StateGraph(WorkflowState)
    builder.add_node("research_plan", research_plan_node)
    builder.add_node("extract_document", extract_document_node)
    builder.add_node("evidence_merge", evidence_merge_node)
    builder.add_node("screening", screening_node)
    builder.add_node("memo", memo_node)
    builder.add_node("counter_case", counter_case_node)
    builder.add_node("truth_gap", truth_gap_node)
    builder.add_node("verdict_brief", verdict_brief_node)
    builder.add_edge(START, "research_plan")
    builder.add_conditional_edges("research_plan", fan_out_evidence)
    builder.add_edge("extract_document", "evidence_merge")
    builder.add_edge("evidence_merge", "screening")
    builder.add_edge("screening", "memo")
    builder.add_edge("memo", "counter_case")
    builder.add_edge("counter_case", "truth_gap")
    builder.add_conditional_edges(
        "truth_gap",
        after_truth_gap,
        {"brief": "verdict_brief", "end": END},
    )
    builder.add_edge("verdict_brief", END)
    return builder.compile()


def run_workflow(payload: WorkflowState) -> WorkflowState:
    """Run the graph, or a compatible bounded fallback if LangGraph is absent."""

    if StateGraph is None:
        return run_sequential_fallback(payload)
    return create_workflow().invoke(payload)


def run_sequential_fallback(payload: WorkflowState) -> WorkflowState:
    """Fallback preserves the same stage order but is only used without LangGraph."""

    state: WorkflowState = dict(payload)

    def apply(node: Any) -> None:
        update = node(state)
        trace = update.pop("trace", [])
        state.update(update)
        state["trace"] = [*state.get("trace", []), *trace]

    apply(research_plan_node)
    batches = []
    for document in state.get("documents", []):
        update = extract_document_node({"deal": state["deal"], "document": document})
        batches.extend(update["evidence_batches"])
        state["trace"] = [*state.get("trace", []), *update["trace"]]
    state["evidence_batches"] = batches
    apply(evidence_merge_node)
    for node in [
        screening_node,
        memo_node,
        counter_case_node,
        truth_gap_node,
    ]:
        apply(node)
    if state.get("include_verdict_brief", False):
        apply(verdict_brief_node)
    return state
