"""
Implements: EXECUTION_ROLES_SPEC.md, section 7 (Task Result — Schema v0)

Scope (v0):
- Field-level validation for Task Result v0, and only what is explicitly specified
  in EXECUTION_ROLES_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Spec commonly shows wrapper form:
    task_result: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"task_result": <task_result object>}
    B) direct task_result object (mapping that contains at least 'schema_version')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_TASK_RESULT_V0,
    fail,
    require_enum_str,
    require_key,
    require_mapping,
    require_str,
)


def _require_list_of_mappings(x: Any, path: str) -> list[Mapping[str, Any]]:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        if not isinstance(item, Mapping):
            raise TypeError(f"{path}[{i}]: expected object/dict")
    return x  # type: ignore[return-value]


def _get_task_result_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"task_result": <mapping>}, or
      - direct task_result object (mapping that contains at least 'schema_version').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "task_result")
    if "task_result" in root:
        return require_mapping(root["task_result"], "task_result.task_result")
    if "schema_version" not in root:
        fail("task_result: expected wrapper {'task_result': {...}} or direct object with 'schema_version'")
    return root


def validate_task_result_v0(obj: Any) -> None:
    """
    Validate Task Result v0.

    Required sections:
    - schema_version
    - identity (includes task_id)
    - execution_role
    - status
    - output
    - errors
    """
    tr = _get_task_result_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(tr, "schema_version", "task_result"),
        "task_result.schema_version",
        [SCHEMA_TASK_RESULT_V0],
    )

    # -----------------------------
    # identity (required)
    # -----------------------------
    identity = require_mapping(require_key(tr, "identity", "task_result"), "task_result.identity")
    require_str(require_key(identity, "envelope_id", "task_result.identity"), "task_result.identity.envelope_id")
    require_str(require_key(identity, "req_id", "task_result.identity"), "task_result.identity.req_id")
    require_str(require_key(identity, "trace_id", "task_result.identity"), "task_result.identity.trace_id")
    require_str(require_key(identity, "task_id", "task_result.identity"), "task_result.identity.task_id")

    # -----------------------------
    # execution_role (required)
    # -----------------------------
    require_str(require_key(tr, "execution_role", "task_result"), "task_result.execution_role")

    # -----------------------------
    # status (required)
    # -----------------------------
    status = require_enum_str(
        require_key(tr, "status", "task_result"),
        "task_result.status",
        ["success", "failure"],
    )

    # -----------------------------
    # output (required)
    # -----------------------------
    output = require_mapping(require_key(tr, "output", "task_result"), "task_result.output")
    require_enum_str(
        require_key(output, "type", "task_result.output"),
        "task_result.output.type",
        ["text", "structured", "empty"],
    )
    # payload key must exist; content is not validated here
    if "payload" not in output:
        fail("task_result.output.payload: missing required key 'payload'")

    # -----------------------------
    # errors (required)
    # -----------------------------
    errors = _require_list_of_mappings(
        require_key(tr, "errors", "task_result"),
        "task_result.errors",
    )

    for i, e in enumerate(errors):
        path = f"task_result.errors[{i}]"
        ed = require_mapping(e, path)
        require_str(require_key(ed, "code", path), f"{path}.code")
        require_str(require_key(ed, "message", path), f"{path}.message")

    # -----------------------------
    # Invariants explicitly stated in spec
    # -----------------------------
    if status == "success":
        if len(errors) != 0:
            fail("task_result.errors: must be empty when status='success'")
    else:
        if len(errors) == 0:
            fail("task_result.errors: must be non-empty when status='failure'")
