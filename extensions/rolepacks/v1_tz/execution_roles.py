from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from validation.schemas import (
    SCHEMA_TASK_INSTRUCTION_V0,
    SCHEMA_TASK_RESULT_SET_V0,
    SCHEMA_TASK_RESULT_V0,
    validate_artifact_v0,
)

from ._v0_validator_shim import ensure_v0_validators_importable


class ExecutionRolesError(ValueError):
    pass


def _normalize_input(input_artifact: Any, *, artifact: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
    if artifact is not None:
        return artifact
    if isinstance(input_artifact, Mapping):
        return input_artifact
    raise ExecutionRolesError("execution_roles: input artifact must be a mapping")


def _extract_task_instructions(bundle: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    tis = bundle.get("task_instructions")
    if not isinstance(tis, list):
        raise ExecutionRolesError("execution_roles: expected 'task_instructions' list in input bundle")
    out: List[Mapping[str, Any]] = []
    for i, item in enumerate(tis):
        if not isinstance(item, Mapping):
            raise ExecutionRolesError(f"execution_roles: task_instructions[{i}] must be a mapping")
        out.append(item)
    if len(out) == 0:
        raise ExecutionRolesError("execution_roles: task_instructions must be non-empty")
    return out


def execution_roles(
    input_artifact: Any = None,
    run_context: Any = None,
    *,
    artifact: Optional[Mapping[str, Any]] = None,
    **_: Any,
) -> Dict[str, Any]:
    """
    Live Execution Roles (universal) — rolepack v1_tz

    Input:
      - bundle with task_instruction_v0[] (from role_orchestrator)

    Output:
      - task_result_set_v0

    Behavior:
      - deterministic
      - fail-closed
      - no LLM
      - each task -> Task Result (status=success)
      - output payload: deterministic template text
    """
    ensure_v0_validators_importable()

    bundle = _normalize_input(input_artifact, artifact=artifact)
    task_instructions = _extract_task_instructions(bundle)

    # Validate every task_instruction strictly (fail-closed)
    for ti in task_instructions:
        validate_artifact_v0(artifact=ti, expected_schema_version=SCHEMA_TASK_INSTRUCTION_V0)

    # Identity: from the first instruction (all should match by construction)
    first_identity = task_instructions[0]["identity"]
    envelope_id = first_identity["envelope_id"]
    req_id = first_identity["req_id"]
    trace_id = first_identity["trace_id"]

    results: List[Dict[str, Any]] = []

    # Deterministic iteration order: stable sort by task_id
    # (Even if upstream already ordered, this guarantees determinism.)
    sorted_tis = sorted(task_instructions, key=lambda x: str(x["identity"]["task_id"]))

    for ti in sorted_tis:
        identity = ti["identity"]
        task_id = identity["task_id"]
        exec_role = ti["execution_role"]
        desc = ti["task_description"]

        body = f"Executed {exec_role} for {task_id}: {desc}"

        task_result: Dict[str, Any] = {
            "schema_version": SCHEMA_TASK_RESULT_V0,
            "identity": {
                "envelope_id": identity["envelope_id"],
                "req_id": identity["req_id"],
                "trace_id": identity["trace_id"],
                "task_id": task_id,
            },
            "execution_role": exec_role,
            "status": "success",
            "output": {
                "type": "text",
                "payload": body,
            },
            "errors": [],
        }

        # Validate each task_result strictly (optional, but fail-closed is better)
        validate_artifact_v0(artifact=task_result, expected_schema_version=SCHEMA_TASK_RESULT_V0)

        # task_result_set_v0 требует results[i] = {"task_result": <obj>}
        results.append({"task_result": task_result})

    task_result_set: Dict[str, Any] = {
        "schema_version": SCHEMA_TASK_RESULT_SET_V0,
        "identity": {
            "envelope_id": envelope_id,
            "req_id": req_id,
            "trace_id": trace_id,
        },
        "results": results,
        "handoff": {
            "target_role": "result_assembler",
        },
    }

    validate_artifact_v0(artifact=task_result_set, expected_schema_version=SCHEMA_TASK_RESULT_SET_V0)
    return task_result_set
