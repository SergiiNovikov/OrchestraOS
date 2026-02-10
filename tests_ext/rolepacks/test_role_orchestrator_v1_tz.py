from __future__ import annotations

import pytest

from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

ensure_v0_validators_importable()

from validation.schemas import (  # noqa: E402
    SCHEMA_EXECUTION_PLAN_V0,
    SCHEMA_TASK_GRAPH_V0,
    SCHEMA_TASK_INSTRUCTION_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_tz.role_orchestrator import role_orchestrator  # noqa: E402


def make_task_graph(tasks) -> dict:
    return {
        "schema_version": SCHEMA_TASK_GRAPH_V0,
        "identity": {
            "envelope_id": "env1",
            "req_id": "req1",
            "trace_id": "trace1",
        },
        "source_fingerprint": {"baseline_norm_hash": "hash123"},
        "task_graph": {"tasks": tasks},
        "handoff": {"target_role": "role_orchestrator"},
    }


@pytest.mark.parametrize(
    "tasks",
    [
        # 1 task
        [{"task_id": "t1", "description": "Explain the architecture", "depends_on": []}],
        # 2 tasks linear
        [
            {"task_id": "t1", "description": "Extract goal and constraints", "depends_on": []},
            {"task_id": "t2", "description": "Draft minimal plan", "depends_on": ["t1"]},
        ],
        # 3 tasks linear
        [
            {"task_id": "t1", "description": "Determine required code changes", "depends_on": []},
            {"task_id": "t2", "description": "Implement minimal patch", "depends_on": ["t1"]},
            {"task_id": "t3", "description": "Add tests (pytest)", "depends_on": ["t2"]},
        ],
        # 3 tasks branching into final
        [
            {"task_id": "t1", "description": "Gather requirements", "depends_on": []},
            {"task_id": "t2", "description": "Write code", "depends_on": ["t1"]},
            {"task_id": "t3", "description": "Write docs", "depends_on": ["t1"]},
        ],
        # tie-break ordering case
        [
            {"task_id": "a", "description": "Plan milestone steps", "depends_on": []},
            {"task_id": "b", "description": "Explain why tests fail", "depends_on": []},
            {"task_id": "c", "description": "Implement fix", "depends_on": ["a", "b"]},
        ],
        # different task_ids
        [
            {"task_id": "x1", "description": "Explain determinism", "depends_on": []},
            {"task_id": "x2", "description": "Make a plan", "depends_on": ["x1"]},
        ],
        # mixed language
        [
            {"task_id": "t1", "description": "Сделай план на 3 шага", "depends_on": []},
            {"task_id": "t2", "description": "Реализуй минимальный патч", "depends_on": ["t1"]},
        ],
        # all independent
        [
            {"task_id": "t1", "description": "Explain", "depends_on": []},
            {"task_id": "t2", "description": "Plan", "depends_on": []},
            {"task_id": "t3", "description": "Implement code", "depends_on": []},
        ],
        # chain with non t1 ids
        [
            {"task_id": "p1", "description": "Plan", "depends_on": []},
            {"task_id": "p2", "description": "Implement", "depends_on": ["p1"]},
            {"task_id": "p3", "description": "Test", "depends_on": ["p2"]},
        ],
        # another 2 tasks
        [
            {"task_id": "k1", "description": "Fix bug in validator", "depends_on": []},
            {"task_id": "k2", "description": "Add pytest coverage", "depends_on": ["k1"]},
        ],
    ],
)
def test_role_orchestrator_golden(tasks) -> None:
    tg = make_task_graph(tasks)

    out = role_orchestrator(artifact=tg)

    assert "execution_plan" in out
    assert "task_instructions" in out

    validate_artifact_v0(artifact=out["execution_plan"], expected_schema_version=SCHEMA_EXECUTION_PLAN_V0)
    for ti in out["task_instructions"]:
        validate_artifact_v0(artifact=ti, expected_schema_version=SCHEMA_TASK_INSTRUCTION_V0)


def test_role_orchestrator_determinism_n3() -> None:
    tg = make_task_graph(
        [
            {"task_id": "t1", "description": "Determine required code changes", "depends_on": []},
            {"task_id": "t2", "description": "Implement minimal patch", "depends_on": ["t1"]},
            {"task_id": "t3", "description": "Add tests (pytest)", "depends_on": ["t2"]},
        ]
    )

    out1 = role_orchestrator(artifact=tg)
    out2 = role_orchestrator(artifact=tg)
    out3 = role_orchestrator(artifact=tg)

    assert out1 == out2 == out3


def test_role_orchestrator_fail_closed_cycle() -> None:
    tg = make_task_graph(
        [
            {"task_id": "t1", "description": "A", "depends_on": ["t2"]},
            {"task_id": "t2", "description": "B", "depends_on": ["t1"]},
        ]
    )

    with pytest.raises(Exception):
        role_orchestrator(artifact=tg)
