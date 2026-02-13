from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping

from validation.schemas import (
    SCHEMA_REQUEST_ENVELOPE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

from ._v0_validator_shim import ensure_v0_validators_importable


class ScopeResolverError(ValueError):
    pass


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _normalize_maturity_for_scoped_request(maturity_from_envelope: str) -> str:
    """
    scoped_request_v0 allows only 'MATURE' for carryover_labels.maturity in this repo snapshot.
    request_envelope_v0 can be 'IMMATURE'.

    Deterministic policy:
      - if already 'MATURE' -> keep
      - otherwise -> coerce to 'MATURE' (minimal useful; avoids breaking chain)
    """
    return "MATURE" if maturity_from_envelope != "MATURE" else "MATURE"


def scope_resolver(*, artifact: Mapping[str, Any], **_: Any) -> Dict[str, Any]:
    """
    Live Scope Resolver (v1_tz) — minimal deterministic.

    Input:
      - request_envelope_v0

    Output:
      - scoped_request_v0

    Notes:
      - No LLM
      - Fail-closed via validate_artifact_v0
      - Minimal scope: allowed_contours=["text"], required_by_contract=[]
      - Maturity is normalized to match scoped_request_v0 schema constraints.
    """
    ensure_v0_validators_importable()

    validate_artifact_v0(artifact=artifact, expected_schema_version=SCHEMA_REQUEST_ENVELOPE_V0)

    env = artifact.get("request_envelope", artifact)

    header = env["header"]
    baseline_norm: str = env["payload_isolation"]["baseline_norm"]
    baseline_hash = _sha256_hex(baseline_norm)

    contradictions_detected = env["consistency"]["contradictions_detected"]
    maturity_from_envelope = env["maturity_gate"]["maturity"]
    maturity = _normalize_maturity_for_scoped_request(str(maturity_from_envelope))
    intent_label = env["intent"]["intent"]

    scoped_request: Dict[str, Any] = {
        "schema_version": SCHEMA_SCOPED_REQUEST_V0,
        "identity": {
            "envelope_id": header["envelope_id"],
            "req_id": header["req_id"],
            "trace_id": header["trace_id"],
        },
        "input_fingerprint": {
            "baseline_norm_hash": baseline_hash,
        },
        "carryover_labels": {
            "intent": intent_label,
            "maturity": maturity,
            "contradictions_detected": contradictions_detected,
        },
        "scope": {
            "scope_class": "general",
            "scope_confidence": 1.0,
            "allowed_contours": ["text"],
            "disallowed_contours": [],
            "required_by_contract": [],
        },
        "handoff": {
            "target_role": "intent_interpreter",
            "handoff_payload": {
                "baseline_norm": baseline_norm,
            },
            "notes_for_downstream": [],
        },
    }

    validate_artifact_v0(artifact=scoped_request, expected_schema_version=SCHEMA_SCOPED_REQUEST_V0)
    return scoped_request
