"""Bounded LangGraph orchestration for The VC Brain.

The graph is intentionally a fixed DAG:
research plan -> parallel evidence extraction -> claim validation -> screening -> memo -> counter-case
-> truth-gap verification -> optional brief -> human review outside the graph.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from . import core, memory, runtime
from .model_router import LUNA_MODEL, TERRA_MODEL

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
    evidence_validation: dict[str, Any]
    founder_profiles: list[dict[str, Any]]
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


def evidence_verify_node(state: WorkflowState) -> WorkflowState:
    verification = runtime.endpoint_evidence_verify(
        {"deal": state["deal"], "evidence": state.get("evidence", [])}
    )
    intake = state["deal"].get("intake") if isinstance(state["deal"].get("intake"), dict) else {}
    founder_names = intake.get("founder_names") if isinstance(intake.get("founder_names"), list) else []
    founder_evidence = [item for item in verification["evidence"] if item.get("evidence_type") == "founder"]
    founder_profiles = [
        memory.endpoint_founder_memory_upsert(
            {"founder_name": str(name), "evidence": founder_evidence}
        )
        for name in founder_names
        if str(name).strip()
    ]
    return {
        "evidence": verification["evidence"],
        "evidence_validation": verification,
        "founder_profiles": founder_profiles,
        "trace": ["evidence_verify:terra:claim_trust"],
    }


def screening_node(state: WorkflowState) -> WorkflowState:
    return {
        "screening": runtime.endpoint_screen_score(
            {
                "deal": state["deal"],
                "evidence": state.get("evidence", []),
                "founder_profiles": state.get("founder_profiles", []),
            }
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
    builder.add_node("evidence_verify", evidence_verify_node)
    builder.add_node("screening", screening_node)
    builder.add_node("memo", memo_node)
    builder.add_node("counter_case", counter_case_node)
    builder.add_node("truth_gap", truth_gap_node)
    builder.add_node("verdict_brief", verdict_brief_node)
    builder.add_edge(START, "research_plan")
    builder.add_conditional_edges("research_plan", fan_out_evidence)
    builder.add_edge("extract_document", "evidence_merge")
    builder.add_edge("evidence_merge", "evidence_verify")
    builder.add_edge("evidence_verify", "screening")
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
        result = run_sequential_fallback(payload)
    else:
        result = create_workflow().invoke(payload)
    return {**result, "audit_events": workflow_audit_events(result)}


def workflow_audit_events(result: WorkflowState) -> list[dict[str, Any]]:
    """Expose fixed-stage provenance without exposing model chain-of-thought."""

    deal = result.get("deal") if isinstance(result.get("deal"), dict) else {}
    run_id = str(deal.get("deal_id") or "")
    evidence = result.get("evidence") if isinstance(result.get("evidence"), list) else []
    validation = result.get("evidence_validation") if isinstance(result.get("evidence_validation"), dict) else {}
    screening = result.get("screening") if isinstance(result.get("screening"), dict) else {}
    memo = result.get("memo") if isinstance(result.get("memo"), dict) else {}
    adversary = result.get("adversary_report") if isinstance(result.get("adversary_report"), dict) else {}
    truth_gap = result.get("truth_gap_verification") if isinstance(result.get("truth_gap_verification"), dict) else {}
    brief = result.get("verdict_brief") if isinstance(result.get("verdict_brief"), dict) else {}
    evidence_ids = [str(item.get("evidence_id")) for item in evidence if isinstance(item, dict) and item.get("evidence_id")]
    events = [
        core.audit_trace_event(
            stage="research.plan",
            run_id=run_id,
            model=LUNA_MODEL,
            input_reference_ids=[run_id],
            status_detail="Generated a bounded research plan.",
        ),
        core.audit_trace_event(
            stage="evidence.extract",
            run_id=run_id,
            model=LUNA_MODEL,
            input_reference_ids=[run_id],
            output_reference_ids=evidence_ids,
            status_detail="Extracted source-backed evidence from supplied documents.",
        ),
        core.audit_trace_event(
            stage="evidence.verify",
            run_id=run_id,
            model=TERRA_MODEL,
            input_reference_ids=evidence_ids,
            output_reference_ids=[str(validation.get("validation_id") or "")],
            status_detail="Assigned claim-level trust and contradiction states.",
        ),
        core.audit_trace_event(
            stage="screen.score",
            run_id=run_id,
            model=TERRA_MODEL,
            input_reference_ids=evidence_ids,
            output_reference_ids=[str(screening.get("deal_id") or "")],
            status_detail="Produced independent, non-averaged opportunity axes.",
        ),
        core.audit_trace_event(
            stage="memo.write",
            run_id=run_id,
            model=TERRA_MODEL,
            input_reference_ids=evidence_ids,
            output_reference_ids=[str(memo.get("memo_id") or "")],
            status_detail="Wrote the evidence-grounded memo and explicit data gaps.",
        ),
        core.audit_trace_event(
            stage="adversary.write",
            run_id=run_id,
            model=TERRA_MODEL,
            input_reference_ids=[str(memo.get("memo_id") or "")],
            output_reference_ids=[str(adversary.get("report_id") or "")],
            status_detail="Generated one bounded counter-case; no debate loop was run.",
        ),
        core.audit_trace_event(
            stage="truth_gap.verify",
            run_id=run_id,
            model=TERRA_MODEL,
            input_reference_ids=[str(adversary.get("report_id") or "")],
            output_reference_ids=[str(truth_gap.get("verification_id") or "")],
            status_detail="Badged counter-case objections against shared Memory evidence.",
        ),
    ]
    if brief:
        events.append(
            core.audit_trace_event(
                stage="verdict.brief",
                run_id=run_id,
                model=LUNA_MODEL,
                input_reference_ids=[str(truth_gap.get("verification_id") or "")],
                output_reference_ids=[str(brief.get("brief_id") or "")],
                status_detail="Generated a non-authoritative reviewer brief.",
            )
        )
    return events


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
        evidence_verify_node,
        screening_node,
        memo_node,
        counter_case_node,
        truth_gap_node,
    ]:
        apply(node)
    if state.get("include_verdict_brief", False):
        apply(verdict_brief_node)
    return state
