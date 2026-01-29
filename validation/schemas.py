"""
Implements: REFERENCE_IMPLEMENTATION_STRUCTURE_v0.md, section 6 (validation/ is contract checks, fail-closed)
Implements: RUNTIME_POLICIES_v0.md, section 6 (fail-closed structured errors) — wiring-level only
Implements: IMPLEMENTATION_GUIDELINES_v0.md, section 6 (taxonomy, propagation) — wiring-level only

Scope (v0):
- Central registry ("dispatch") of artifact validators by schema_version.
- Fail-closed helpers used by validators.
- NO duplication of full artifact structures here.
  Detailed field-level validation lives in artifacts/*_v0.py (1 file = 1 schema).

Rules:
- Unknown schema_version -> ValueError (fail-closed).
- Validators MUST raise on any mismatch (no coercion, no best-effort).
- This module contains no role logic and no runtime orchestration.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Sequence

# -----------------------------
# Schema version identifiers (v0)
# -----------------------------

SCHEMA_REQUEST_ENVELOPE_V0 = "request_envelope_v0"
SCHEMA_SCOPED_REQUEST_V0 = "scoped_request_v0"
SCHEMA_INTENT_PACKAGE_V0 = "intent_package_v0"
SCHEMA_TASK_GRAPH_V0 = "task_graph_v0"
SCHEMA_EXECUTION_PLAN_V0 = "execution_plan_v0"
SCHEMA_TASK_INSTRUCTION_V0 = "task_instruction_v0"
SCHEMA_TASK_RESULT_V0 = "task_result_v0"
SCHEMA_TASK_RESULT_SET_V0 = "task_result_set_v0"
SCHEMA_FINAL_RESPONSE_ARTIFACT_V0 = "final_response_artifact_v0"


# -----------------------------
# Fail-closed primitive checks
# -----------------------------


def fail(msg: str) -> None:
    raise ValueError(msg)


def is_mapping(x: Any) -> bool:
    return isinstance(x, Mapping)


def require_mapping(x: Any, path: str) -> Mapping[str, Any]:
    if not is_mapping(x):
        raise TypeError(f"{path}: expected object/dict")
    return x  # type: ignore[return-value]


def require_key(obj: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in obj:
        fail(f"{path}: missing required key '{key}'")
    return obj[key]


def require_str(x: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(x, str):
        raise TypeError(f"{path}: expected string")
    if not allow_empty and x == "":
        fail(f"{path}: must be non-empty string")
    return x


def require_bool(x: Any, path: str) -> bool:
    if not isinstance(x, bool):
        raise TypeError(f"{path}: expected boolean")
    return x


def require_int(x: Any, path: str) -> int:
    # bool is subclass of int -> exclude
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{path}: expected integer")
    return x


def require_enum_str(x: Any, path: str, allowed: Sequence[str]) -> str:
    s = require_str(x, path)
    if s not in allowed:
        fail(f"{path}: invalid value '{s}', allowed: {list(allowed)}")
    return s


def require_optional_str(x: Any, path: str) -> Optional[str]:
    if x is None:
        return None
    return require_str(x, path)


# -----------------------------
# Validator registry (v0)
# -----------------------------

ValidatorFn = Callable[[Any], None]


def _load_validators_v0() -> Dict[str, ValidatorFn]:
    """
    Lazy-import validators from artifacts/*_v0.py.

    Why lazy:
    - Allows building repo incrementally (schemas registry first, then artifacts).
    - Avoids import errors before artifacts modules exist.

    Contract:
    - Each artifacts/*_v0.py MUST expose validate_<artifact>_v0(obj: Any) -> None
    """
    validators: Dict[str, ValidatorFn] = {}

    # Import inside function to keep module import-safe during incremental build.
    from artifacts.request_envelope_v0 import validate_request_envelope_v0
    from artifacts.scoped_request_v0 import validate_scoped_request_v0
    from artifacts.intent_package_v0 import validate_intent_package_v0
    from artifacts.task_graph_v0 import validate_task_graph_v0
    from artifacts.execution_plan_v0 import validate_execution_plan_v0
    from artifacts.task_instruction_v0 import validate_task_instruction_v0
    from artifacts.task_result_v0 import validate_task_result_v0
    from artifacts.task_result_set_v0 import validate_task_result_set_v0
    from artifacts.final_response_artifact_v0 import validate_final_response_artifact_v0

    validators[SCHEMA_REQUEST_ENVELOPE_V0] = validate_request_envelope_v0
    validators[SCHEMA_SCOPED_REQUEST_V0] = validate_scoped_request_v0
    validators[SCHEMA_INTENT_PACKAGE_V0] = validate_intent_package_v0
    validators[SCHEMA_TASK_GRAPH_V0] = validate_task_graph_v0
    validators[SCHEMA_EXECUTION_PLAN_V0] = validate_execution_plan_v0
    validators[SCHEMA_TASK_INSTRUCTION_V0] = validate_task_instruction_v0
    validators[SCHEMA_TASK_RESULT_V0] = validate_task_result_v0
    validators[SCHEMA_TASK_RESULT_SET_V0] = validate_task_result_set_v0
    validators[SCHEMA_FINAL_RESPONSE_ARTIFACT_V0] = validate_final_response_artifact_v0

    return validators


def validate_artifact_v0(*, artifact: Any, expected_schema_version: str) -> None:
    """
    Validate artifact against the expected schema version.

    Fail-closed:
    - Unknown schema version -> ValueError
    - Any mismatch -> exception from underlying validator
    """
    require_str(expected_schema_version, "expected_schema_version")

    validators = _load_validators_v0()
    if expected_schema_version not in validators:
        fail(f"expected_schema_version: unsupported '{expected_schema_version}'")

    validators[expected_schema_version](artifact)
