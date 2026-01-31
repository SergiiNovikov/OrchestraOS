"""
Implements: SCOPE_RESOLVER_SPEC.md, section 8.1 (Scoped Request — Schema v0)
Implements: SCOPE_RESOLVER_SPEC.md, section 7.2 (Policy override: if policy_flags not empty -> requires secondary_scope_class)
Implements: SCOPE_RESOLVER_SPEC.md, section 9 (Invariants: baseline_norm passthrough; notes_for_downstream constraints-only) — shape-level only

Scope (v0):
- Field-level validation for Scoped Request v0, and only what is explicitly specified
  in SCOPE_RESOLVER_SPEC.md §8.1 (+ one explicit conditional from §7.2 about policy_flags).
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Spec expresses wrapper form:
    scoped_request: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"scoped_request": <scoped_request object>}
    B) direct scoped_request object (mapping that contains at least 'identity')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_SCOPED_REQUEST_V0,
    fail,
    require_bool,
    require_enum_str,
    require_int,
    require_key,
    require_mapping,
    require_optional_str,
    require_str,
)


def _require_number_0_1(x: Any, path: str) -> None:
    if x is None:
        raise TypeError(f"{path}: expected number")
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{path}: expected number")
    v = float(x)
    if not (0.0 <= v <= 1.0):
        fail(f"{path}: must be in [0, 1]")


def _require_list_of_non_empty_str(x: Any, path: str) -> None:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        require_str(item, f"{path}[{i}]")


def _get_scoped_request_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"scoped_request": <mapping>}, or
      - direct scoped_request object (mapping that contains at least 'identity').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "scoped_request")
    if "scoped_request" in root:
        return require_mapping(root["scoped_request"], "scoped_request.scoped_request")
    # direct form must look like scoped_request
    if "identity" not in root:
        fail("scoped_request: expected wrapper {'scoped_request': {...}} or direct scoped_request object with 'identity'")
    return root


def validate_scoped_request_v0(obj: Any) -> None:
    """
    Validate Scoped Request v0.

    Implements: SCOPE_RESOLVER_SPEC.md §8.1

    Required sections:
    - schema_version
    - identity
    - input_fingerprint
    - carryover_labels
    - scope
    - handoff

    Conditional / optional fields:
    - identity.determinism_key (string?)
    - input_fingerprint.language (string?)
    - carryover_labels.policy_flags (list[enum]?)
    - carryover_labels.contradictions_summary (list[text]?)
    - scope.secondary_scope_class (enum?)
    """
    sr = _get_scoped_request_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(sr, "schema_version", "scoped_request"),
        "scoped_request.schema_version",
        [SCHEMA_SCOPED_REQUEST_V0],
    )

    # identity (required; determinism_key optional)
    identity = require_mapping(require_key(sr, "identity", "scoped_request"), "scoped_request.identity")
    require_str(require_key(identity, "envelope_id", "scoped_request.identity"), "scoped_request.identity.envelope_id")
    require_str(require_key(identity, "req_id", "scoped_request.identity"), "scoped_request.identity.req_id")
    require_str(require_key(identity, "trace_id", "scoped_request.identity"), "scoped_request.identity.trace_id")
    if "determinism_key" in identity:
        require_optional_str(identity["determinism_key"], "scoped_request.identity.determinism_key")

    # input_fingerprint (required)
    inf = require_mapping(require_key(sr, "input_fingerprint", "scoped_request"), "scoped_request.input_fingerprint")
    require_str(
        require_key(inf, "baseline_norm_hash", "scoped_request.input_fingerprint"),
        "scoped_request.input_fingerprint.baseline_norm_hash",
    )
    if "language" in inf:
        require_optional_str(inf["language"], "scoped_request.input_fingerprint.language")

    # carryover_labels (required)
    cl = require_mapping(require_key(sr, "carryover_labels", "scoped_request"), "scoped_request.carryover_labels")
    require_str(require_key(cl, "intent", "scoped_request.carryover_labels"), "scoped_request.carryover_labels.intent")
    require_enum_str(
        require_key(cl, "maturity", "scoped_request.carryover_labels"),
        "scoped_request.carryover_labels.maturity",
        ["MATURE"],
    )

    policy_flags_len = 0
    if "policy_flags" in cl and cl["policy_flags"] is not None:
        _require_list_of_non_empty_str(cl["policy_flags"], "scoped_request.carryover_labels.policy_flags")
        policy_flags_len = len(cl["policy_flags"])

    contradictions_detected = require_bool(
        require_key(cl, "contradictions_detected", "scoped_request.carryover_labels"),
        "scoped_request.carryover_labels.contradictions_detected",
    )
    if "contradictions_summary" in cl and cl["contradictions_summary"] is not None:
        _require_list_of_non_empty_str(cl["contradictions_summary"], "scoped_request.carryover_labels.contradictions_summary")
        # No extra semantics enforced beyond schema (do not infer emptiness rules from contradictions_detected).
        _ = contradictions_detected

    # scope (required)
    scope = require_mapping(require_key(sr, "scope", "scoped_request"), "scoped_request.scope")
    require_str(require_key(scope, "scope_class", "scoped_request.scope"), "scoped_request.scope.scope_class")
    if "secondary_scope_class" in scope:
        require_optional_str(scope["secondary_scope_class"], "scoped_request.scope.secondary_scope_class")

    # Explicit conditional from §7.2: if policy_flags not empty -> secondary_scope_class required.
    if policy_flags_len > 0:
        if "secondary_scope_class" not in scope or scope["secondary_scope_class"] in (None, ""):
            fail("scoped_request.scope.secondary_scope_class: required when carryover_labels.policy_flags is non-empty")

    _require_number_0_1(require_key(scope, "scope_confidence", "scoped_request.scope"), "scoped_request.scope.scope_confidence")

    _require_list_of_non_empty_str(
        require_key(scope, "allowed_contours", "scoped_request.scope"),
        "scoped_request.scope.allowed_contours",
    )
    _require_list_of_non_empty_str(
        require_key(scope, "disallowed_contours", "scoped_request.scope"),
        "scoped_request.scope.disallowed_contours",
    )
    _require_list_of_non_empty_str(
        require_key(scope, "required_by_contract", "scoped_request.scope"),
        "scoped_request.scope.required_by_contract",
    )

    # handoff (required)
    handoff = require_mapping(require_key(sr, "handoff", "scoped_request"), "scoped_request.handoff")
    require_enum_str(
        require_key(handoff, "target_role", "scoped_request.handoff"),
        "scoped_request.handoff.target_role",
        ["intent_interpreter"],
    )
    hp = require_mapping(require_key(handoff, "handoff_payload", "scoped_request.handoff"), "scoped_request.handoff.handoff_payload")
    require_str(
        require_key(hp, "baseline_norm", "scoped_request.handoff.handoff_payload"),
        "scoped_request.handoff.handoff_payload.baseline_norm",
    )
    _require_list_of_non_empty_str(
        require_key(handoff, "notes_for_downstream", "scoped_request.handoff"),
        "scoped_request.handoff.notes_for_downstream",
    )
