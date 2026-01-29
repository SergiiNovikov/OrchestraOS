"""
Implements: ERROR_CODE_DICTIONARY_v0.md, sections 2, 3, 4, 5
Implements: RUNTIME_POLICIES_v0.md, section 6 (fail-closed structured errors)
Implements: IMPLEMENTATION_GUIDELINES_v0.md, section 6 (taxonomy, propagation)

Scope:
- Canonical runtime error representation for Reference Implementation v0.
- Fail-closed validation against the fixed v0 error taxonomy.
- Factory helpers to construct errors without semantic drift.

Rules:
- error_code MUST be from ERROR_CODE_DICTIONARY_v0.md (v0).
- error_class MUST match the dictionary entry for the given error_code.
- Roles/runtime MUST NOT invent new error codes in v0.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ErrorClass(str, Enum):
    """Implements: ERROR_CODE_DICTIONARY_v0.md, section 3 (error_class)."""

    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    INVALID_INPUT = "INVALID_INPUT"
    RUNTIME_FAILURE = "RUNTIME_FAILURE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"


# Fixed v0 error dictionary (code -> class), copied normatively from ERROR_CODE_DICTIONARY_v0.md.
# Implements: ERROR_CODE_DICTIONARY_v0.md, section 4 (v0 taxonomy).
_ERROR_CODE_TO_CLASS_V0: Dict[str, ErrorClass] = {
    # 4.1 GLOBAL
    "GLOBAL_MISSING_INPUT": ErrorClass.INVALID_INPUT,
    "GLOBAL_SCHEMA_INVALID": ErrorClass.CONTRACT_VIOLATION,
    "GLOBAL_UNSUPPORTED_VERSION": ErrorClass.UNSUPPORTED_VERSION,
    "GLOBAL_DETERMINISM_MISMATCH": ErrorClass.CONTRACT_VIOLATION,
    # 4.2 Scope / Intent / Planning
    "INTENT_NOT_RESOLVED": ErrorClass.CONTRACT_VIOLATION,
    "SCOPE_VIOLATION": ErrorClass.CONTRACT_VIOLATION,
    "TASK_GRAPH_INVALID": ErrorClass.CONTRACT_VIOLATION,
    # 4.3 Orchestration
    "NO_EXECUTION_ROLE": ErrorClass.CONTRACT_VIOLATION,
    "MULTIPLE_EXECUTORS": ErrorClass.CONTRACT_VIOLATION,
    "EXECUTION_PLAN_INVALID": ErrorClass.CONTRACT_VIOLATION,
    # 4.4 Execution
    "TASK_EXECUTION_FAILED": ErrorClass.RUNTIME_FAILURE,
    "TASK_INPUT_INSUFFICIENT": ErrorClass.INVALID_INPUT,
    "TASK_NON_DETERMINISTIC": ErrorClass.CONTRACT_VIOLATION,
    # 4.5 Aggregation / Finalization
    "RESULT_SET_INCOMPLETE": ErrorClass.CONTRACT_VIOLATION,
    "RESULT_IDENTITY_MISMATCH": ErrorClass.CONTRACT_VIOLATION,
    "FINAL_ASSEMBLY_FAILED": ErrorClass.RUNTIME_FAILURE,
}


def is_valid_error_code_v0(error_code: str) -> bool:
    """Return True iff error_code is a known v0 code."""
    return isinstance(error_code, str) and error_code in _ERROR_CODE_TO_CLASS_V0


def expected_error_class_v0(error_code: str) -> ErrorClass:
    """
    Return expected ErrorClass for a v0 error_code.

    Raises:
        ValueError: if error_code is unknown (fail-closed).
    """
    if not is_valid_error_code_v0(error_code):
        raise ValueError(f"Unknown v0 error_code: {error_code!r}")
    return _ERROR_CODE_TO_CLASS_V0[error_code]


def validate_error_taxonomy_v0(*, error_code: str, error_class: ErrorClass) -> None:
    """
    Fail-closed validation of (error_code, error_class) against v0 dictionary.

    Raises:
        ValueError: if code unknown or class mismatch.
        TypeError: if error_class not an ErrorClass.
    """
    if not isinstance(error_class, ErrorClass):
        raise TypeError(f"error_class must be ErrorClass, got: {type(error_class).__name__}")
    expected = expected_error_class_v0(error_code)
    if error_class != expected:
        raise ValueError(
            f"error_class mismatch for {error_code!r}: expected {expected.value}, got {error_class.value}"
        )


@dataclass(frozen=True)
class RuntimeErrorV0(Exception):
    """
    Structured runtime error for v0.

    Implements: ERROR_CODE_DICTIONARY_v0.md, section 2 (error structure).

    Note (v0 correctness):
    - This dataclass subclasses Exception. For correctness with traceback/printing/pickling,
      we MUST set Exception.args deterministically.
    - We do this in __post_init__ via object.__setattr__ (compatible with frozen=True).

    Fields:
        error_code: string identifier from the v0 dictionary.
        error_class: ErrorClass (must match dictionary for code).
        role_id: role emitting/owning the failure (runtime may use infrastructure role_id).
        artifact_expected: expected artifact type/version (string identifier).
        determinism_key: determinism_key for the run (read-only context).
        message: minimal diagnostics (no speculation).
    """

    error_code: str
    error_class: ErrorClass
    role_id: str
    artifact_expected: str
    determinism_key: str
    message: str

    def __post_init__(self) -> None:
        # Fail-closed taxonomy validation.
        validate_error_taxonomy_v0(error_code=self.error_code, error_class=self.error_class)

        # Minimal structural validation (fail-closed).
        if not isinstance(self.role_id, str) or not self.role_id:
            raise ValueError("role_id must be a non-empty string")
        if not isinstance(self.artifact_expected, str) or not self.artifact_expected:
            raise ValueError("artifact_expected must be a non-empty string")
        if not isinstance(self.determinism_key, str) or not self.determinism_key:
            raise ValueError("determinism_key must be a non-empty string")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("message must be a non-empty string")

        # Critical: ensure Exception base is initialized deterministically.
        # Minimal safe v0 fix: set args = (message,)
        object.__setattr__(self, "args", (self.message,))

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to a plain dict (machine-readable).

        NOTE: This is a runtime helper; it does not introduce new schema beyond
        the normative fields of the v0 error structure.
        """
        return {
            "error": {
                "error_code": self.error_code,
                "error_class": self.error_class.value,
                "role_id": self.role_id,
                "artifact_expected": self.artifact_expected,
                "determinism_key": self.determinism_key,
                "message": self.message,
            }
        }


def make_error_v0(
    *,
    error_code: str,
    role_id: str,
    artifact_expected: str,
    determinism_key: str,
    message: str,
    override_error_class: Optional[ErrorClass] = None,
) -> RuntimeErrorV0:
    """
    Generic factory for RuntimeErrorV0.

    Default behavior:
    - error_class is derived from the fixed v0 dictionary by error_code.

    Fail-closed:
    - If override_error_class is provided, it MUST match the dictionary.
    """
    derived = expected_error_class_v0(error_code)
    if override_error_class is not None:
        validate_error_taxonomy_v0(error_code=error_code, error_class=override_error_class)
        error_class = override_error_class
    else:
        error_class = derived

    return RuntimeErrorV0(
        error_code=error_code,
        error_class=error_class,
        role_id=role_id,
        artifact_expected=artifact_expected,
        determinism_key=determinism_key,
        message=message,
    )


def invalid_input(
    *,
    error_code: str,
    role_id: str,
    artifact_expected: str,
    determinism_key: str,
    message: str,
) -> RuntimeErrorV0:
    """
    Factory: INVALID_INPUT.

    Fail-closed: error_code MUST map to INVALID_INPUT in v0 dictionary.
    """
    return make_error_v0(
        error_code=error_code,
        role_id=role_id,
        artifact_expected=artifact_expected,
        determinism_key=determinism_key,
        message=message,
        override_error_class=ErrorClass.INVALID_INPUT,
    )


def contract_violation(
    *,
    error_code: str,
    role_id: str,
    artifact_expected: str,
    determinism_key: str,
    message: str,
) -> RuntimeErrorV0:
    """
    Factory: CONTRACT_VIOLATION.

    Fail-closed: error_code MUST map to CONTRACT_VIOLATION in v0 dictionary.
    """
    return make_error_v0(
        error_code=error_code,
        role_id=role_id,
        artifact_expected=artifact_expected,
        determinism_key=determinism_key,
        message=message,
        override_error_class=ErrorClass.CONTRACT_VIOLATION,
    )


def runtime_failure(
    *,
    error_code: str,
    role_id: str,
    artifact_expected: str,
    determinism_key: str,
    message: str,
) -> RuntimeErrorV0:
    """
    Factory: RUNTIME_FAILURE.

    Fail-closed: error_code MUST map to RUNTIME_FAILURE in v0 dictionary.
    """
    return make_error_v0(
        error_code=error_code,
        role_id=role_id,
        artifact_expected=artifact_expected,
        determinism_key=determinism_key,
        message=message,
        override_error_class=ErrorClass.RUNTIME_FAILURE,
    )


def unsupported_version(
    *,
    error_code: str,
    role_id: str,
    artifact_expected: str,
    determinism_key: str,
    message: str,
) -> RuntimeErrorV0:
    """
    Factory: UNSUPPORTED_VERSION.

    Fail-closed: error_code MUST map to UNSUPPORTED_VERSION in v0 dictionary.
    """
    return make_error_v0(
        error_code=error_code,
        role_id=role_id,
        artifact_expected=artifact_expected,
        determinism_key=determinism_key,
        message=message,
        override_error_class=ErrorClass.UNSUPPORTED_VERSION,
    )
