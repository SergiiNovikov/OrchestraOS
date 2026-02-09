from __future__ import annotations

from typing import Any, Mapping, Dict

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

from ._v0_validator_shim import ensure_v0_validators_importable


class IntentInterpreterError(ValueError):
    pass


def intent_interpreter(
    *,
    artifact: Mapping[str, Any],
    **_: Any,
) -> Dict[str, Any]:
    """
    Live Intent Interpreter (rolepack v1_tz)

    Input:
      - scoped_request_v0

    Output:
      - intent_package_v0

    Properties:
      - deterministic
      - fail-closed
      - schema-pure
    """

    # Workaround for missing artifacts.task_graph_v0 in this repo snapshot:
    # v0 validate_artifact_v0 lazily imports all validators and crashes otherwise.
    ensure_v0_validators_importable()

    # -------------------------
    # Validate upstream strictly
    # -------------------------
    validate_artifact_v0(
        artifact=artifact,
        expected_schema_version=SCHEMA_SCOPED_REQUEST_V0,
    )

    # Allow wrapper style {"scoped_request": {...}} or direct artifact
    scoped = artifact.get("scoped_request", artifact)

    identity = scoped["identity"]
    handoff_payload = scoped["handoff"]["handoff_payload"]

    baseline_norm: str = handoff_payload["baseline_norm"]
    baseline_hash: str = scoped["input_fingerprint"]["baseline_norm_hash"]

    # -------------------------
    # Minimal deterministic intent resolution
    # -------------------------
    text = baseline_norm.lower().strip()

    if not text:
        intent_status = "AMBIGUOUS"
        ambiguity = ["empty input"]
    else:
        intent_status = "RESOLVED"
        ambiguity = []

    # -------------------------
    # Build Intent Package v0
    # -------------------------
    intent_package: Dict[str, Any] = {
        "schema_version": SCHEMA_INTENT_PACKAGE_V0,
        "identity": {
            "envelope_id": identity["envelope_id"],
            "req_id": identity["req_id"],
            "trace_id": identity["trace_id"],
        },
        "source_fingerprint": {
            "baseline_norm_hash": baseline_hash,
        },
        "intent_definition": {
            "intent_status": intent_status,
            "constraints": {
                "allowed_contours": scoped["scope"]["allowed_contours"],
                "required_by_contract": scoped["scope"]["required_by_contract"],
            },
        },
        "ambiguity_report": {
            "ambiguous": bool(ambiguity),
            "ambiguity_reason": ambiguity or None,
        },
        "conflict_report": {
            "conflicts_present": False,
            "conflict_summary": None,
        },
        "handoff": {
            "target_role": "task_decomposer",
            "notes_for_downstream": [
                f"baseline_norm='{baseline_norm}'",
            ],
        },
    }

    # -------------------------
    # Validate output strictly
    # -------------------------
    validate_artifact_v0(
        artifact=intent_package,
        expected_schema_version=SCHEMA_INTENT_PACKAGE_V0,
    )

    return intent_package
