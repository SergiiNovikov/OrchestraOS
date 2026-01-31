"""
Implements: RESULT_ASSEMBLER_SPEC.md, section "Task Result Set — Schema v0"

Scope (v0):
- Field-level validation for Task Result Set v0, and only what is explicitly specified
  in RESULT_ASSEMBLER_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- To stay aligned with the central registry in validation/schemas.py, this validator uses
  wrapper form:
      task_results: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"task_results": <task_results object>}
    B) direct task_results object (mapping that contains at least 'schema_version')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_TASK_RESULT_SET_V0,
    fail,
    require_enum_str,
    require_key,
    require_mapping,
    require_optional_str,
    require_str,
)

from artifacts.task_result_v0 import validate_task_result_v0


def _require_list_of_mappings(x: Any, path: str) -> list[Mapping[str, Any]]:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        if not isinstance(item, Mapping):
            raise TypeError(f"{path}[{i}]: expected object/dict")
    return x  # type: ignore[return-value]


def _get_task_results_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"task_results": <mapping>}, or
      - direct task_results object (mapping that contains at least 'schema_version').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "task_results")
    if "task_results" in root:
        return require_mapping(root["task_results"], "task_results.task_results")
    if "schema_version" not in root:
        fail("task_results: expected wrapper {'task_results': {...}} or direct object with 'schema_version'")
    return root


def validate_task_result_set_v0(obj: Any) -> None:
    """
    Validate Task Result Set v0.

    Required sections:
    - schema_version
    - identity
    - results
    """
    trs = _get_task_results_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(trs, "schema_version", "task_results"),
        "task_results.schema_version",
        [SCHEMA_TASK_RESULT_SET_V0],
    )

    # -----------------------------
    # identity (required; determinism_key optional)
    # -----------------------------
    identity = require_mapping(require_key(trs, "identity", "task_results"), "task_results.identity")
    require_str(require_key(identity, "envelope_id", "task_results.identity"), "task_results.identity.envelope_id")
    require_str(require_key(identity, "req_id", "task_results.identity"), "task_results.identity.req_id")
    require_str(require_key(identity, "trace_id", "task_results.identity"), "task_results.identity.trace_id")
    if "determinism_key" in identity:
        require_optional_str(identity["determinism_key"], "task_results.identity.determinism_key")

    # -----------------------------
    # results (required, non-empty)
    # -----------------------------
    results = _require_list_of_mappings(
        require_key(trs, "results", "task_results"),
        "task_results.results",
    )
    if len(results) == 0:
        fail("task_results.results: must be non-empty list")

    for i, item in enumerate(results):
        path = f"task_results.results[{i}]"
        mapping = require_mapping(item, path)
        if "task_result" not in mapping:
            fail(f"{path}: missing required key 'task_result'")
        validate_task_result_v0(mapping["task_result"])
