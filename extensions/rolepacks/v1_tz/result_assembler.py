from __future__ import annotations

from typing import Any, Dict, Mapping

from validation.schemas import (
    SCHEMA_FINAL_RESPONSE_ARTIFACT_V0,
    SCHEMA_TASK_RESULT_SET_V0,
    validate_artifact_v0,
)

from ._v0_validator_shim import ensure_v0_validators_importable


class ResultAssemblerError(ValueError):
    pass


def result_assembler(*, artifact: Mapping[str, Any], **_: Any) -> Dict[str, Any]:
    """
    Live Result Assembler (v1_tz) — minimal deterministic.

    Input:
      - task_result_set_v0

    Output:
      - final_response_artifact_v0

    Logic:
      - execution_status.status = "success" iff all task_result.status == "success"
      - results passthrough: same list items {"task_result": {...}} (schema-compatible)
    """
    ensure_v0_validators_importable()

    validate_artifact_v0(artifact=artifact, expected_schema_version=SCHEMA_TASK_RESULT_SET_V0)

    trs = artifact.get("task_results", artifact)

    identity = trs["identity"]
    results = trs["results"]

    all_success = True
    for item in results:
        tr = item["task_result"]
        if tr.get("status") != "success":
            all_success = False
            break

    final_response: Dict[str, Any] = {
        "schema_version": SCHEMA_FINAL_RESPONSE_ARTIFACT_V0,
        "identity": {
            "envelope_id": identity["envelope_id"],
            "req_id": identity["req_id"],
            "trace_id": identity["trace_id"],
        },
        "execution_status": {
            "status": "success" if all_success else "failure",
        },
        "results": results,
    }

    validate_artifact_v0(artifact=final_response, expected_schema_version=SCHEMA_FINAL_RESPONSE_ARTIFACT_V0)
    return final_response
