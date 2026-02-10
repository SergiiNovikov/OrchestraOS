from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_TASK_GRAPH_V0,
    validate_artifact_v0,
)

from ._v0_validator_shim import ensure_v0_validators_importable


class TaskDecomposerError(ValueError):
    pass


def _extract_baseline_norm_from_notes(notes: List[str]) -> str:
    """
    Intent Interpreter (Milestone 1) writes:
      "baseline_norm='<text>'"
    Deterministic parse, fail-closed if not found.
    """
    for s in notes:
        if s.startswith("baseline_norm='") and s.endswith("'") and len(s) >= len("baseline_norm=''"):
            return s[len("baseline_norm='"):-1]
    raise TaskDecomposerError("intent_package.handoff.notes_for_downstream: missing baseline_norm marker")


def _classify_minimal(text: str) -> str:
    """
    Minimal deterministic classifier for task decomposition.
    Returns one of: "question", "plan", "code", "generic"
    """
    t = text.strip().lower()
    if not t:
        return "generic"
    if t.endswith("?") or t.startswith(("how ", "why ", "what ", "when ", "где", "как", "почему", "что", "зачем")):
        return "question"
    if any(x in t for x in ("milestone", "план", "roadmap", "шаг", "задач", "тз")):
        return "plan"
    if any(x in t for x in ("код", "implement", "реализ", "fix", "bug", "pytest", "test")):
        return "code"
    return "generic"


def _make_tasks(kind: str, *, intent_status: str) -> List[Dict[str, Any]]:
    """
    Minimal useful decomposition:
      - If intent not RESOLVED -> 1 task asking for clarification / unblock
      - Else -> 2 or 3 tasks based on kind
    Deterministic task_ids: t1,t2,t3
    """
    if intent_status in ("AMBIGUOUS", "BLOCKED"):
        return [
            {
                "task_id": "t1",
                "description": "Clarify intent and constraints; request missing details if needed.",
                "depends_on": [],
            }
        ]

    if kind == "question":
        return [
            {"task_id": "t1", "description": "Identify what the user is asking and required context.", "depends_on": []},
            {"task_id": "t2", "description": "Produce an accurate answer grounded in the provided context/spec.", "depends_on": ["t1"]},
        ]

    if kind == "plan":
        return [
            {"task_id": "t1", "description": "Extract the goal and constraints for the requested plan.", "depends_on": []},
            {"task_id": "t2", "description": "Draft a minimal actionable plan (1–3 steps) matching constraints.", "depends_on": ["t1"]},
            {"task_id": "t3", "description": "Add test/validation checkpoints and deterministic acceptance criteria.", "depends_on": ["t2"]},
        ]

    if kind == "code":
        return [
            {"task_id": "t1", "description": "Determine required code changes within allowed directories only.", "depends_on": []},
            {"task_id": "t2", "description": "Implement the minimal patch (fail-closed, deterministic).", "depends_on": ["t1"]},
            {"task_id": "t3", "description": "Add/adjust tests in tests_ext to cover golden + determinism.", "depends_on": ["t2"]},
        ]

    # generic
    return [
        {"task_id": "t1", "description": "Understand the request and constraints.", "depends_on": []},
        {"task_id": "t2", "description": "Produce the minimal useful output that satisfies the request.", "depends_on": ["t1"]},
    ]


def task_decomposer(
    *,
    artifact: Mapping[str, Any],
    **_: Any,
) -> Dict[str, Any]:
    """
    Live Task Decomposer (rolepack v1_tz)

    Input:
      - intent_package_v0

    Output:
      - task_graph_v0 (validated by v0 validator; in this repo snapshot proxied via shim)

    Properties:
      - deterministic
      - fail-closed
      - schema-pure
      - minimal useful decomposition (1–3 tasks)
    """
    ensure_v0_validators_importable()

    validate_artifact_v0(
        artifact=artifact,
        expected_schema_version=SCHEMA_INTENT_PACKAGE_V0,
    )

    ip = artifact.get("intent_package", artifact)

    identity = ip["identity"]
    baseline_hash = ip["source_fingerprint"]["baseline_norm_hash"]

    handoff = ip["handoff"]
    notes: List[str] = handoff["notes_for_downstream"]
    baseline_norm = _extract_baseline_norm_from_notes(notes)

    intent_status: str = ip["intent_definition"]["intent_status"]

    kind = _classify_minimal(baseline_norm)
    tasks = _make_tasks(kind, intent_status=intent_status)

    task_graph: Dict[str, Any] = {
        "schema_version": SCHEMA_TASK_GRAPH_V0,
        "identity": {
            "envelope_id": identity["envelope_id"],
            "req_id": identity["req_id"],
            "trace_id": identity["trace_id"],
        },
        "source_fingerprint": {
            "baseline_norm_hash": baseline_hash,
        },
        "task_graph": {
            "tasks": tasks,
        },
        "handoff": {
            "target_role": "role_orchestrator",
        },
    }

    validate_artifact_v0(
        artifact=task_graph,
        expected_schema_version=SCHEMA_TASK_GRAPH_V0,
    )

    return task_graph
