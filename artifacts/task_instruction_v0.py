"""
Implements: ROLE_ORCHESTRATOR_SPEC.md, section "Task Instruction — Schema v0"
Implements: EXECUTION_ROLES_SPEC.md, section 4 (Task Instruction input contract)

Scope (v0):
- Field-level validation for Task Instruction v0, and only what is explicitly specified
  in ROLE_ORCHESTRATOR_SPEC.md / EXECUTION_ROLES_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Spec commonly shows wrapper form:
    task_instruction: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"task_instruction": <task_instruction object>}
    B) direct task_instruction object (mapping that contains at least 'schema_version')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_TASK_INSTRUCTION_V0,
    fail,
    require_enum_str,
    require_key,
    require_mapping,
    require_str,
)


def _require_list_of_non_empty_str(x: Any, path: str) -> None:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        require_str(item, f"{path}[{i}]")


def _get_task_instruction_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"task_instruction": <mapping>}, or
      - direct task_instruction object (mapping that contains at least 'schema_version').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "task_instruction")
    if "task_instruction" in root:
        return require_mapping(root["task_instruction"], "task_instruction.task_instruction")
    if "schema_version" not in root:
        fail("task_instruction: expected wrapper {'task_instruction': {...}} or direct object with 'schema_version'")
    return root


def validate_task_instruction_v0(obj: Any) -> None:
    """
    Validate Task Instruction v0.

    Required sections:
    - schema_version
    - identity (includes task_id)
    - execution_role
    - task_description
    - depends_on
    """
    ti = _get_task_instruction_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(ti, "schema_version", "task_instruction"),
        "task_instruction.schema_version",
        [SCHEMA_TASK_INSTRUCTION_V0],
    )

    # identity (required)
    identity = require_mapping(require_key(ti, "identity", "task_instruction"), "task_instruction.identity")
    require_str(require_key(identity, "envelope_id", "task_instruction.identity"), "task_instruction.identity.envelope_id")
    require_str(require_key(identity, "req_id", "task_instruction.identity"), "task_instruction.identity.req_id")
    require_str(require_key(identity, "trace_id", "task_instruction.identity"), "task_instruction.identity.trace_id")
    require_str(require_key(identity, "task_id", "task_instruction.identity"), "task_instruction.identity.task_id")

    # execution_role (required)
    require_str(require_key(ti, "execution_role", "task_instruction"), "task_instruction.execution_role")

    # task_description (required)
    require_str(require_key(ti, "task_description", "task_instruction"), "task_instruction.task_description")

    # depends_on (required, list[str])
    deps = require_key(ti, "depends_on", "task_instruction")
    _require_list_of_non_empty_str(deps, "task_instruction.depends_on")
