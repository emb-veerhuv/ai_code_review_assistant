from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .analyzers import (
    generate_docs,
    scan_checklist,
    scan_classes,
    scan_includes,
    scan_repository,
)
from .llm_review import analyze_with_llm
from .models import ReviewState


def checklist_node(
    state: ReviewState,
):
    findings = []

    for path, text in state["files"].items():
        findings.extend(
            scan_checklist(
                path,
                text,
                state["rules"],
            )
        )

    return {
        "findings": findings,
    }


def structure_node(
    state: ReviewState,
):
    findings = scan_repository(
        list(state["files"]),
        state["files"],
        state["rules"],
    )

    return {
        "findings": findings,
    }


def cpp_node(
    state: ReviewState,
):
    findings = []

    for path, text in state["files"].items():
        findings.extend(
            scan_classes(
                path,
                text,
                state["rules"],
            )
        )

        findings.extend(
            scan_includes(
                path,
                text,
                state["rules"],
            )
        )

    return {
        "findings": findings,
    }


def documentation_node(
    state: ReviewState,
):
    documentation = []

    for path, text in state["files"].items():
        documentation.extend(
            generate_docs(
                path,
                text,
            )
        )

    return {
        "patches": documentation,
    }


def llm_node(
    state: ReviewState,
):
    return analyze_with_llm(state)


def aggregate_node(
    state: ReviewState,
):
    unique = {}
    combined = (
        state.get("findings", [])
        + state.get("llm_findings", [])
    )

    severity_rank = {
        "Blocker": 0,
        "High": 1,
        "Medium": 2,
        "Low": 3,
    }

    for item in combined:
        key = (
            item.get("file"),
            item.get(
                "start_line",
                item.get("line", 1),
            ),
            item.get("rule_id"),
        )
        unique[key] = item

    findings = sorted(
        unique.values(),
        key=lambda item: (
            severity_rank.get(
                item.get(
                    "severity",
                    "Low",
                ),
                9,
            ),
            item.get("file", ""),
            item.get(
                "start_line",
                item.get("line", 1),
            ),
        ),
    )

    return {
        "findings": findings,
        "summary": {
            "files": len(
                state.get(
                    "files",
                    {},
                )
            ),
            "findings": len(findings),
            "high_risk": sum(
                item.get("severity")
                in {"Blocker", "High"}
                for item in findings
            ),
            "llm_enabled": state.get(
                "llm_enabled",
                False,
            ),
            "llm_status": state.get(
                "llm_status",
                "",
            ),
        },
    }


def build_graph():
    graph = StateGraph(ReviewState)

    graph.add_node(
        "checklist",
        checklist_node,
    )
    graph.add_node(
        "structure",
        structure_node,
    )
    graph.add_node(
        "cpp",
        cpp_node,
    )
    graph.add_node(
        "documentation",
        documentation_node,
    )
    graph.add_node(
        "llm_review",
        llm_node,
    )
    graph.add_node(
        "aggregate",
        aggregate_node,
    )

    graph.add_edge(
        START,
        "checklist",
    )
    graph.add_edge(
        START,
        "structure",
    )
    graph.add_edge(
        START,
        "cpp",
    )

    graph.add_edge(
        "checklist",
        "documentation",
    )
    graph.add_edge(
        "structure",
        "documentation",
    )
    graph.add_edge(
        "cpp",
        "documentation",
    )

    graph.add_edge(
        "documentation",
        "llm_review",
    )

    graph.add_edge(
        "llm_review",
        "aggregate",
    )

    graph.add_edge(
        "aggregate",
        END,
    )

    return graph.compile()


review_graph = build_graph()
