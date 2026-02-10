from __future__ import annotations

import pytest

from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

ensure_v0_validators_importable()

from validation.schemas import (  # noqa: E402
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_TASK_GRAPH_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_tz.task_decomposer import task_decomposer  # noqa: E402


def make_intent_package(text: str, *, intent_status: str = "RESOLVED") -> dict:
    return {
        "schema_version": SCHEMA_INTENT_PACKAGE_V0,
        "identity": {
            "envelope_id": "env1",
            "req_id": "req1",
            "trace_id": "trace1",
        },
        "source_fingerprint": {
            "baseline_norm_hash": "hash123",
        },
        "intent_definition": {
            "intent_status": intent_status,
            "constraints": {
                "allowed_contours": ["text"],
                "required_by_contract": [],
            },
        },
        "ambiguity_report": {
            "ambiguous": intent_status != "RESOLVED",
            "ambiguity_reason": ["needs clarification"] if intent_status != "RESOLVED" else None,
        },
        "conflict_report": {
            "conflicts_present": False,
            "conflict_summary": None,
        },
        "handoff": {
            "target_role": "task_decomposer",
            "notes_for_downstream": [
                f"baseline_norm='{text}'",
            ],
        },
    }


@pytest.mark.parametrize(
    "text",
    [
        "How does determinism work?",
        "Make a plan for Milestone 2",
        "Fix failing pytest tests",
        "Explain validation failure?",
        "Сделай план на 3 шага",
        "Реализуй минимальный патч",
        "What happens next?",
        "Summarize this spec",
        "Implement task decomposer role",
        "Почему падают тесты?",
    ],
)
def test_task_decomposer_golden(text: str) -> None:
    ip = make_intent_package(text, intent_status="RESOLVED")

    out = task_decomposer(artifact=ip)

    validate_artifact_v0(
        artifact=out,
        expected_schema_version=SCHEMA_TASK_GRAPH_V0,
    )


def test_task_decomposer_ambiguity_min_1_task() -> None:
    ip = make_intent_package("", intent_status="AMBIGUOUS")
    out = task_decomposer(artifact=ip)

    validate_artifact_v0(artifact=out, expected_schema_version=SCHEMA_TASK_GRAPH_V0)

    tg = out.get("task_graph_package", out).get("task_graph", out["task_graph"])
    assert len(tg["tasks"]) == 1
    assert tg["tasks"][0]["task_id"] == "t1"


def test_task_decomposer_determinism_n3() -> None:
    ip = make_intent_package("Make a plan for Milestone 2", intent_status="RESOLVED")

    out1 = task_decomposer(artifact=ip)
    out2 = task_decomposer(artifact=ip)
    out3 = task_decomposer(artifact=ip)

    assert out1 == out2 == out3
