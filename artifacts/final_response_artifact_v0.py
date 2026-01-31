"""
Implements: RESULT_ASSEMBLER_SPEC.md, section "Final Response Artifact — Schema v0"

Scope (v0):
- Field-level validation for Final Response Artifact v0, and only what is explicitly specified
  in RESULT_ASSEMBLER_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- To stay aligned with the central registry in validation/schemas.py, this validator uses
  wrapper form:
      final_response: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"final_response": <final_response object>}
    B) direct final_response object (mapping that contains at least 'schema_version')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_FINAL_RESPONSE_ARTIFACT_V0,
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


def _get_final_response_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"final_response": <mapping>}, or
      - direct final_response object (mapping that contains at least 'schema_version').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "final_response")
    if "final_response" in root:
        return require_mapping(root["final_response"], "final_response.final_response")
    if "schema_version" not in root:
        fail("final_response: expected wrapper {'final_response': {...}} or direct object with 'schema_version'")
    return root


def validate_final_response_artifact_v0(obj: Any) -> None:
    """
    Validate Final Response Artifact v0.

    Required sections:
    - schema_version
    - identity
    - execution_status
    - results
    """
    fr = _get_final_response_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(fr, "schema_version", "final_response"),
        "final_response.schema_version",
        [SCHEMA_FINAL_RESPONSE_ARTIFACT_V0],
    )

    # -----------------------------
    # identity (required; determinism_key optional)
    # -----------------------------
    identity = require_mapping(require_key(fr, "identity", "final_response"), "final_response.identity")
    require_str(require_key(identity, "envelope_id", "final_response.identity"), "final_response.identity.envelope_id")
    require_str(require_key(identity, "req_id", "final_response.identity"), "final_response.identity.req_id")
    require_str(require_key(identity, "trace_id", "final_response.identity"), "final_response.identity.trace_id")
    if "determinism_key" in identity:
        require_optional_str(identity["determinism_key"], "final_response.identity.determinism_key")

    # -----------------------------
    # execution_status (required)
    # -----------------------------
    es = require_mapping(require_key(fr, "execution_status", "final_response"), "final_response.execution_status")
    require_enum_str(
        require_key(es, "status", "final_response.execution_status"),
        "final_response.execution_status.status",
        ["success", "failure"],
    )

    # -----------------------------
    # results (required, non-empty)
    # -----------------------------
    results = _require_list_of_mappings(
        require_key(fr, "results", "final_response"),
        "final_response.results",
    )
    if len(results) == 0:
        fail("final_response.results: must be non-empty list")

    for i, item in enumerate(results):
        path = f"final_response.results[{i}]"
        mapping = require_mapping(item, path)
        if "task_result" not in mapping:
            fail(f"{path}: missing required key 'task_result'")
        validate_task_result_v0(mapping["task_result"])
