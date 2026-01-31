"""
Implements: ROLE_ORCHESTRATOR_SPEC.md, section "Execution Plan — Schema v0"

Scope (v0):
- Field-level validation for Execution Plan v0, and only what is explicitly specified
  in ROLE_ORCHESTRATOR_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Spec commonly shows wrapper form:
    execution_plan: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"execution_plan": <execution_plan object>}
    B) direct execution_plan object (mapping that contains at least 'schema_version')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_EXECUTION_PLAN_V0,
    fail,
    require_enum_str,
    require_int,
    require_key,
    require_mapping,
    require_optional_str,
    require_str,
)


def _require_list_of_mappings(x: Any, path: str) -> list[Mapping[str, Any]]:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        if not isinstance(item, Mapping):
            raise TypeError(f"{path}[{i}]: expected object/dict")
    return x  # type: ignore[return-value]


def _get_execution_plan_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"execution_plan": <mapping>}, or
      - direct execution_plan object (mapping that contains at least 'schema_version').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "execution_plan")
    if "execution_plan" in root:
        return require_mapping(root["execution_plan"], "execution_plan.execution_plan")
    if "schema_version" not in root:
        fail("execution_plan: expected wrapper {'execution_plan': {...}} or direct object with 'schema_version'")
    return root


def validate_execution_plan_v0(obj: Any) -> None:
    """
    Validate Execution Plan v0.

    Implements: ROLE_ORCHESTRATOR_SPEC.md

    Required sections:
    - schema_version
    - identity
    - tasks
    """
    ep = _get_execution_plan_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(ep, "schema_version", "execution_plan"),
        "execution_plan.schema_version",
        [SCHEMA_EXECUTION_PLAN_V0],
    )

    # -----------------------------
    # identity (required; determinism_key optional)
    # -----------------------------
    identity = require_mapping(require_key(ep, "identity", "execution_plan"), "execution_plan.identity")
    require_str(require_key(identity, "envelope_id", "execution_plan.identity"), "execution_plan.identity.envelope_id")
    require_str(require_key(identity, "req_id", "execution_plan.identity"), "execution_plan.identity.req_id")
    require_str(require_key(identity, "trace_id", "execution_plan.identity"), "execution_plan.identity.trace_id")
    if "determinism_key" in identity:
        require_optional_str(identity["determinism_key"], "execution_plan.identity.determinism_key")

    # -----------------------------
    # tasks (required, non-empty)
    # -----------------------------
    tasks = _require_list_of_mappings(
        require_key(ep, "tasks", "execution_plan"),
        "execution_plan.tasks",
    )
    if len(tasks) == 0:
        fail("execution_plan.tasks: must be non-empty list")

    seen_task_ids: set[str] = set()
    seen_order_indexes: set[int] = set()

    for i, t in enumerate(tasks):
        path = f"execution_plan.tasks[{i}]"
        td = require_mapping(t, path)

        task_id = require_str(require_key(td, "task_id", path), f"{path}.task_id")
        if task_id in seen_task_ids:
            fail(f"{path}.task_id: duplicate '{task_id}'")
        seen_task_ids.add(task_id)

        require_str(require_key(td, "execution_role", path), f"{path}.execution_role")

        order_index = require_int(require_key(td, "order_index", path), f"{path}.order_index")
        if order_index in seen_order_indexes:
            fail(f"{path}.order_index: duplicate '{order_index}'")
        seen_order_indexes.add(order_index)
