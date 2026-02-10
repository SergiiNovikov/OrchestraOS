from __future__ import annotations

import pytest

from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

ensure_v0_validators_importable()

from validation.schemas import (  # noqa: E402
    SCHEMA_TASK_INSTRUCTION_V0,
    SCHEMA_TASK_RESULT_SET_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_tz.execution_roles import execution_roles  # noqa: E402


def make_task_instruction(task_id: str, execution_role: str, task_description: str, depends_on=None) -> dict:
    if depends_on is None:
        depends_on = []
    return {
        "schema_version": SCHEMA_TASK_INSTRUCTION_V0,
        "identity": {
            "envelope_id": "env1",
            "req_id": "req1",
            "trace_id": "trace1",
            "task_id": task_id,
        },
        "execution_role": execution_role,
        "task_description": task_description,
        "depends_on": depends_on,
    }


def make_bundle(task_instructions) -> dict:
    return {
        "task_instructions": task_instructions,
        "handoff": {"target_role": "execution_roles"},
    }


@pytest.mark.parametrize(
    "task_instructions",
    [
        # 1
        [make_task_instruction("t1", "exec_explain", "Explain the architecture")],
        # 2
        [
            make_task_instruction("t1", "exec_plan", "Extract goal and constraints"),
            make_task_instruction("t2", "exec_plan", "Draft minimal plan", depends_on=["t1"]),
        ],
        # 3
        [
            make_task_instruction("t1", "exec_code", "Determine required code changes"),
            make_task_instruction("t2", "exec_code", "Implement minimal patch", depends_on=["t1"]),
            make_task_instruction("t3", "exec_code", "Add pytest coverage", depends_on=["t2"]),
        ],
        # 4 mixed
        [
            make_task_instruction("a", "exec_plan", "Plan milestone"),
            make_task_instruction("b", "exec_explain", "Explain why tests fail"),
            make_task_instruction("c", "exec_code", "Implement fix", depends_on=["a", "b"]),
        ],
        # 5
        [make_task_instruction("x1", "exec_generic", "Do the thing")],
        # 6 RU
        [
            make_task_instruction("t1", "exec_plan", "Сделай план на 3 шага"),
            make_task_instruction("t2", "exec_code", "Реализуй минимальный патч", depends_on=["t1"]),
        ],
        # 7
        [
            make_task_instruction("k1", "exec_code", "Fix bug"),
            make_task_instruction("k2", "exec_code", "Add tests", depends_on=["k1"]),
        ],
        # 8
        [
            make_task_instruction("p1", "exec_plan", "Plan"),
            make_task_instruction("p2", "exec_generic", "Write"),
            make_task_instruction("p3", "exec_explain", "Explain"),
        ],
        # 9
        [
            make_task_instruction("z1", "exec_explain", "How does determinism work?"),
            make_task_instruction("z2", "exec_plan", "Make a plan", depends_on=["z1"]),
        ],
        # 10
        [
            make_task_instruction("m1", "exec_code", "Implement execution role"),
            make_task_instruction("m2", "exec_explain", "Describe constraints", depends_on=["m1"]),
        ],
    ],
)
def test_execution_roles_golden(task_instructions) -> None:
    bundle = make_bundle(task_instructions)

    out = execution_roles(artifact=bundle)

    validate_artifact_v0(artifact=out, expected_schema_version=SCHEMA_TASK_RESULT_SET_V0)

    # quick sanity on deterministic template
    results = out.get("task_results", out).get("results", out["results"])
    assert len(results) == len(task_instructions)


def test_execution_roles_determinism_n3() -> None:
    tis = [
        make_task_instruction("t2", "exec_code", "Implement minimal patch", depends_on=["t1"]),
        make_task_instruction("t1", "exec_code", "Determine required code changes"),
        make_task_instruction("t3", "exec_code", "Add pytest coverage", depends_on=["t2"]),
    ]
    bundle = make_bundle(tis)

    out1 = execution_roles(artifact=bundle)
    out2 = execution_roles(artifact=bundle)
    out3 = execution_roles(artifact=bundle)

    assert out1 == out2 == out3
