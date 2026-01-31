"""
Implements: INTENT_INTERPRETER_SPEC.md, section "Intent Package — Schema v0"

Scope (v0):
- Field-level validation for Intent Package v0, and only what is explicitly specified
  in INTENT_INTERPRETER_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Spec commonly shows wrapper form:
    intent_package: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"intent_package": <intent_package object>}
    B) direct intent_package object (mapping that contains at least 'identity')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    fail,
    require_bool,
    require_enum_str,
    require_key,
    require_mapping,
    require_optional_str,
    require_str,
)


def _require_list_of_non_empty_str(x: Any, path: str) -> None:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        require_str(item, f"{path}[{i}]")


def _get_intent_package_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"intent_package": <mapping>}, or
      - direct intent_package object (mapping that contains at least 'identity').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "intent_package")
    if "intent_package" in root:
        return require_mapping(root["intent_package"], "intent_package.intent_package")
    # direct form must look like intent_package
    if "identity" not in root:
        fail("intent_package: expected wrapper {'intent_package': {...}} or direct intent_package object with 'identity'")
    return root


def validate_intent_package_v0(obj: Any) -> None:
    """
    Validate Intent Package v0.

    Implements: INTENT_INTERPRETER_SPEC.md

    Required sections:
    - schema_version
    - identity
    - source_fingerprint
    - intent_definition
    - ambiguity_report
    - conflict_report
    - handoff

    Optional / conditional fields:
    - identity.determinism_key (string?)
    - intent_definition.intent_label (string?)
    - intent_definition.intent_goal (string?)
    - ambiguity_report.ambiguity_reason (list[text]?)
    - conflict_report.conflict_summary (list[text]?)
    """
    ip = _get_intent_package_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(ip, "schema_version", "intent_package"),
        "intent_package.schema_version",
        [SCHEMA_INTENT_PACKAGE_V0],
    )

    # -----------------------------
    # identity (required; determinism_key optional)
    # -----------------------------
    identity = require_mapping(require_key(ip, "identity", "intent_package"), "intent_package.identity")
    require_str(require_key(identity, "envelope_id", "intent_package.identity"), "intent_package.identity.envelope_id")
    require_str(require_key(identity, "req_id", "intent_package.identity"), "intent_package.identity.req_id")
    require_str(require_key(identity, "trace_id", "intent_package.identity"), "intent_package.identity.trace_id")
    if "determinism_key" in identity:
        require_optional_str(identity["determinism_key"], "intent_package.identity.determinism_key")

    # -----------------------------
    # source_fingerprint (required)
    # -----------------------------
    sf = require_mapping(require_key(ip, "source_fingerprint", "intent_package"), "intent_package.source_fingerprint")
    require_str(
        require_key(sf, "baseline_norm_hash", "intent_package.source_fingerprint"),
        "intent_package.source_fingerprint.baseline_norm_hash",
    )

    # -----------------------------
    # intent_definition (required)
    # -----------------------------
    idef = require_mapping(require_key(ip, "intent_definition", "intent_package"), "intent_package.intent_definition")
    intent_status = require_enum_str(
        require_key(idef, "intent_status", "intent_package.intent_definition"),
        "intent_package.intent_definition.intent_status",
        ["RESOLVED", "AMBIGUOUS", "BLOCKED"],
    )

    if "intent_label" in idef:
        require_optional_str(idef["intent_label"], "intent_package.intent_definition.intent_label")

    if "intent_goal" in idef:
        require_optional_str(idef["intent_goal"], "intent_package.intent_definition.intent_goal")

    # constraints (required)
    constraints = require_mapping(
        require_key(idef, "constraints", "intent_package.intent_definition"),
        "intent_package.intent_definition.constraints",
    )
    _require_list_of_non_empty_str(
        require_key(constraints, "allowed_contours", "intent_package.intent_definition.constraints"),
        "intent_package.intent_definition.constraints.allowed_contours",
    )
    _require_list_of_non_empty_str(
        require_key(constraints, "required_by_contract", "intent_package.intent_definition.constraints"),
        "intent_package.intent_definition.constraints.required_by_contract",
    )

    # -----------------------------
    # ambiguity_report (required)
    # -----------------------------
    ar = require_mapping(require_key(ip, "ambiguity_report", "intent_package"), "intent_package.ambiguity_report")
    ambiguous = require_bool(
        require_key(ar, "ambiguous", "intent_package.ambiguity_report"),
        "intent_package.ambiguity_report.ambiguous",
    )
    if "ambiguity_reason" in ar and ar["ambiguity_reason"] is not None:
        _require_list_of_non_empty_str(
            ar["ambiguity_reason"],
            "intent_package.ambiguity_report.ambiguity_reason",
        )
        # Do not enforce extra semantics between ambiguous flag and reasons unless explicitly stated.
        _ = ambiguous

    # -----------------------------
    # conflict_report (required)
    # -----------------------------
    cr = require_mapping(require_key(ip, "conflict_report", "intent_package"), "intent_package.conflict_report")
    conflicts_present = require_bool(
        require_key(cr, "conflicts_present", "intent_package.conflict_report"),
        "intent_package.conflict_report.conflicts_present",
    )
    if "conflict_summary" in cr and cr["conflict_summary"] is not None:
        _require_list_of_non_empty_str(
            cr["conflict_summary"],
            "intent_package.conflict_report.conflict_summary",
        )
        # No inferred emptiness rules unless explicitly specified.
        _ = conflicts_present

    # -----------------------------
    # handoff (required)
    # -----------------------------
    handoff = require_mapping(require_key(ip, "handoff", "intent_package"), "intent_package.handoff")
    require_enum_str(
        require_key(handoff, "target_role", "intent_package.handoff"),
        "intent_package.handoff.target_role",
        ["task_decomposer"],
    )
    _require_list_of_non_empty_str(
        require_key(handoff, "notes_for_downstream", "intent_package.handoff"),
        "intent_package.handoff.notes_for_downstream",
    )

    # keep to prevent lint unused
    _ = intent_status
