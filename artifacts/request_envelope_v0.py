"""
Implements: FRONT_MANAGER_SPEC.md, section 7 (Request Envelope Schema v0)

Scope (v0):
- Field-level validation for Request Envelope v0, and only what is explicitly specified
  in FRONT_MANAGER_SPEC.md §7.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Some specs express artifacts as a wrapper mapping (e.g., scoped_request: {...}).
  FRONT_MANAGER_SPEC.md lists sections without a YAML wrapper.
- To avoid representation drift while staying deterministic, this validator accepts:
    A) envelope object directly (must contain key 'header')
    B) wrapper form {"request_envelope": <envelope object>}
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from validation.schemas import (
    SCHEMA_REQUEST_ENVELOPE_V0,
    fail,
    require_bool,
    require_enum_str,
    require_key,
    require_mapping,
    require_optional_str,
    require_str,
)


_ALLOWED_SOURCE: Sequence[str] = ("user", "system")
_ALLOWED_MODE: Sequence[str] = ("platform", "delivery")
_ALLOWED_MATURITY: Sequence[str] = ("MATURE", "IMMATURE", "INVALID")
_ALLOWED_RECOMMENDED_NEXT: Sequence[str] = ("route", "return_to_user", "enter_discovery")
_ALLOWED_RESOLUTION_TYPE: Sequence[str] = ("clarified_by_user", "removed_ambiguity", "not_resolved")


def _require_list_of_non_empty_str(x: Any, path: str) -> None:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        require_str(item, f"{path}[{i}]")


def _get_envelope_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"request_envelope": <mapping>}, or
      - direct envelope object (mapping that contains at least 'header').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "request_envelope")
    if "request_envelope" in root:
        return require_mapping(root["request_envelope"], "request_envelope.request_envelope")
    # direct form must look like envelope
    if "header" not in root:
        fail("request_envelope: expected wrapper {'request_envelope': {...}} or direct envelope object with 'header'")
    return root


def validate_request_envelope_v0(obj: Any) -> None:
    """
    Validate Request Envelope v0.

    Implements: FRONT_MANAGER_SPEC.md §7

    Required sections:
    - Header
    - Payload Isolation
    - Intent
    - Maturity Gate
    - Consistency

    Conditional / optional sections:
    - Freeze Candidate (conditional on mode=delivery and maturity=MATURE)
    - Routing Hint (optional)
    - Auditability (optional)
    """
    env = _get_envelope_object(obj)

    # Top-level schema_version (v0 dispatch anchor)
    require_enum_str(
        require_key(env, "schema_version", "request_envelope"),
        "request_envelope.schema_version",
        [SCHEMA_REQUEST_ENVELOPE_V0],
    )

    # -----------------------------
    # Header (all fields required)
    # -----------------------------
    header = require_mapping(require_key(env, "header", "request_envelope"), "request_envelope.header")
    require_str(require_key(header, "envelope_id", "request_envelope.header"), "request_envelope.header.envelope_id")
    require_str(require_key(header, "req_id", "request_envelope.header"), "request_envelope.header.req_id")
    require_str(require_key(header, "trace_id", "request_envelope.header"), "request_envelope.header.trace_id")

    # header.schema_version is validated only if present in §7 representation.
    if "schema_version" in header and header["schema_version"] is not None:
        require_enum_str(
            header["schema_version"],
            "request_envelope.header.schema_version",
            [SCHEMA_REQUEST_ENVELOPE_V0],
        )

    require_str(require_key(header, "created_at", "request_envelope.header"), "request_envelope.header.created_at")
    require_enum_str(
        require_key(header, "source", "request_envelope.header"),
        "request_envelope.header.source",
        _ALLOWED_SOURCE,
    )
    mode = require_enum_str(
        require_key(header, "mode", "request_envelope.header"),
        "request_envelope.header.mode",
        _ALLOWED_MODE,
    )

    # -----------------------------
    # Payload Isolation
    # -----------------------------
    payload = require_mapping(require_key(env, "payload_isolation", "request_envelope"), "request_envelope.payload_isolation")
    require_str(
        require_key(payload, "baseline_norm", "request_envelope.payload_isolation"),
        "request_envelope.payload_isolation.baseline_norm",
    )

    if "raw_input_hash" in payload and payload["raw_input_hash"] is not None:
        require_str(payload["raw_input_hash"], "request_envelope.payload_isolation.raw_input_hash")
    if "language" in payload:
        require_optional_str(payload["language"], "request_envelope.payload_isolation.language")

    dci = require_bool(
        require_key(payload, "dialogue_context_included", "request_envelope.payload_isolation"),
        "request_envelope.payload_isolation.dialogue_context_included",
    )
    if dci is not False:
        fail("request_envelope.payload_isolation.dialogue_context_included: must be false")

    # -----------------------------
    # Intent
    # -----------------------------
    intent = require_mapping(require_key(env, "intent", "request_envelope"), "request_envelope.intent")
    require_str(require_key(intent, "intent", "request_envelope.intent"), "request_envelope.intent.intent")
    # intent_confidence (O): enforce only numeric type if present (no range unless explicitly in §7).
    if "intent_confidence" in intent and intent["intent_confidence"] is not None:
        v = intent["intent_confidence"]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TypeError("request_envelope.intent.intent_confidence: expected number")
    if "intent_notes" in intent:
        require_optional_str(intent["intent_notes"], "request_envelope.intent.intent_notes")

    # -----------------------------
    # Maturity Gate
    # -----------------------------
    mg = require_mapping(require_key(env, "maturity_gate", "request_envelope"), "request_envelope.maturity_gate")
    maturity = require_enum_str(
        require_key(mg, "maturity", "request_envelope.maturity_gate"),
        "request_envelope.maturity_gate.maturity",
        _ALLOWED_MATURITY,
    )
    require_str(require_key(mg, "reason_code", "request_envelope.maturity_gate"), "request_envelope.maturity_gate.reason_code")

    # gap_list (C): condition not specified in schema section; validate only if present.
    if "gap_list" in mg and mg["gap_list"] is not None:
        _require_list_of_non_empty_str(mg["gap_list"], "request_envelope.maturity_gate.gap_list")

    # policy_flags (O): list[text]? (enum values are not enumerated here)
    if "policy_flags" in mg and mg["policy_flags"] is not None:
        _require_list_of_non_empty_str(mg["policy_flags"], "request_envelope.maturity_gate.policy_flags")

    require_enum_str(
        require_key(mg, "recommended_next", "request_envelope.maturity_gate"),
        "request_envelope.maturity_gate.recommended_next",
        _ALLOWED_RECOMMENDED_NEXT,
    )

    # -----------------------------
    # Consistency
    # -----------------------------
    cons = require_mapping(require_key(env, "consistency", "request_envelope"), "request_envelope.consistency")
    require_bool(
        require_key(cons, "contradictions_detected", "request_envelope.consistency"),
        "request_envelope.consistency.contradictions_detected",
    )

    # contradictions_summary (C): condition not specified; validate only if present.
    if "contradictions_summary" in cons and cons["contradictions_summary"] is not None:
        _require_list_of_non_empty_str(cons["contradictions_summary"], "request_envelope.consistency.contradictions_summary")

    # resolution_type (C): validate only if present.
    if "resolution_type" in cons and cons["resolution_type"] is not None:
        require_enum_str(cons["resolution_type"], "request_envelope.consistency.resolution_type", _ALLOWED_RESOLUTION_TYPE)

    # -----------------------------
    # Freeze Candidate (C)
    # Present only when mode=delivery and maturity=MATURE.
    # -----------------------------
    has_freeze_candidate = "freeze_candidate" in env and env["freeze_candidate"] is not None
    freeze_required = (mode == "delivery" and maturity == "MATURE")

    if has_freeze_candidate and not freeze_required:
        fail("request_envelope.freeze_candidate: present only when mode=delivery and maturity=MATURE")

    if freeze_required and not has_freeze_candidate:
        fail("request_envelope.freeze_candidate: required when mode=delivery and maturity=MATURE")

    if has_freeze_candidate:
        fc = require_mapping(env["freeze_candidate"], "request_envelope.freeze_candidate")
        require_str(require_key(fc, "goal", "request_envelope.freeze_candidate"), "request_envelope.freeze_candidate.goal")
        require_str(
            require_key(fc, "success_criteria", "request_envelope.freeze_candidate"),
            "request_envelope.freeze_candidate.success_criteria",
        )
        require_str(require_key(fc, "context", "request_envelope.freeze_candidate"), "request_envelope.freeze_candidate.context")
        require_str(require_key(fc, "scope_in", "request_envelope.freeze_candidate"), "request_envelope.freeze_candidate.scope_in")
        require_str(require_key(fc, "scope_out", "request_envelope.freeze_candidate"), "request_envelope.freeze_candidate.scope_out")
        require_str(
            require_key(fc, "constraints", "request_envelope.freeze_candidate"),
            "request_envelope.freeze_candidate.constraints",
        )
        require_str(
            require_key(fc, "acceptance_criteria", "request_envelope.freeze_candidate"),
            "request_envelope.freeze_candidate.acceptance_criteria",
        )
        require_str(
            require_key(fc, "output_format", "request_envelope.freeze_candidate"),
            "request_envelope.freeze_candidate.output_format",
        )

        if "assumptions" in fc and fc["assumptions"] is not None:
            _require_list_of_non_empty_str(fc["assumptions"], "request_envelope.freeze_candidate.assumptions")
        if "open_questions" in fc and fc["open_questions"] is not None:
            _require_list_of_non_empty_str(fc["open_questions"], "request_envelope.freeze_candidate.open_questions")

        freeze_ack = require_bool(
            require_key(fc, "freeze_ack", "request_envelope.freeze_candidate"),
            "request_envelope.freeze_candidate.freeze_ack",
        )
        if freeze_ack is not True:
            fail("request_envelope.freeze_candidate.freeze_ack: must be true")

    # -----------------------------
    # Routing Hint (O)
    # -----------------------------
    if "routing_hint" in env and env["routing_hint"] is not None:
        rh = require_mapping(env["routing_hint"], "request_envelope.routing_hint")
        require_str(require_key(rh, "target_class", "request_envelope.routing_hint"), "request_envelope.routing_hint.target_class")
        require_str(
            require_key(rh, "handoff_payload_type", "request_envelope.routing_hint"),
            "request_envelope.routing_hint.handoff_payload_type",
        )
        if "notes" in rh:
            require_optional_str(rh["notes"], "request_envelope.routing_hint.notes")

    # -----------------------------
    # Auditability (O)
    # -----------------------------
    if "auditability" in env and env["auditability"] is not None:
        au = require_mapping(env["auditability"], "request_envelope.auditability")
        if "gate_checks_passed" in au and au["gate_checks_passed"] is not None:
            _require_list_of_non_empty_str(au["gate_checks_passed"], "request_envelope.auditability.gate_checks_passed")
        if "gate_checks_failed" in au and au["gate_checks_failed"] is not None:
            _require_list_of_non_empty_str(au["gate_checks_failed"], "request_envelope.auditability.gate_checks_failed")
        if "determinism_key" in au and au["determinism_key"] is not None:
            require_str(au["determinism_key"], "request_envelope.auditability.determinism_key")
