"""
Implements: ROLE_MAP_v0.md, section 3 (linear pipeline order)
Implements: SYSTEM_ARCHITECTURE.md, sections 2, 6 (one input -> one output; explicit artifacts only)
Implements: RUNTIME_POLICIES_v0.md, sections 3, 5, 6, 9, 11 (determinism_key, fail-closed, validation gates, manifest)
Implements: RUN_MANIFEST_SCHEMA_v0.md, sections 2-5 (run_manifest_v0, execution_trace, final_outcome)
Implements: IMPLEMENTATION_GUIDELINES_v0.md, sections 4, 7, 9 (determinism usage, trace, replay support)

Scope:
- Runtime pipeline runner for Reference Implementation v0.
- No role implementations here. Runner only orchestrates provided pure role callables.
- Validation is mandatory (fail-closed). Runner requires a validator to be supplied.
- Records a RunManifestV0 with deterministic execution_trace sequencing.

Design constraints (v0):
- No retries, no fallbacks, no heuristics.
- Any ambiguity/missing required information -> fail-closed error.
- Deterministic ordering: fixed role sequence and monotonic seq from RunContextV0.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Tuple

from runtime.canonicalization import artifact_hash
from runtime.determinism import (
    EnvironmentFingerprintV0,
    PolicyFingerprintV0,
    compute_determinism_key_v0,
    compute_guidelines_fingerprint_from_specs_v0,
    compute_policy_fingerprint_from_specs_v0,
    compute_spec_bundle_hash_v0,
)
from runtime.errors import (
    RuntimeErrorV0,
    contract_violation,
    invalid_input,
    runtime_failure,
)
from runtime.run_context import RunContextV0, RunIdentityV0
from runtime.run_manifest import (
    FinalOutcomeStatus,
    ManifestInputArtifactV0,
    ManifestSpecEntryV0,
    RunManifestV0,
)

# v0 rule: determinism_key MUST be present in RuntimeErrorV0.
# If it cannot be computed yet, we use a fixed, non-empty sentinel (deterministic).
_DETERMINISM_KEY_UNAVAILABLE = "unavailable"


class ArtifactValidatorV0(Protocol):
    """
    Validation interface required by runtime runner.

    The validator is responsible for:
    - schema validation of input/output artifacts per role
    - role precondition validation (e.g., scope/maturity gates)
    - fail-closed behavior (raise exceptions on invalid contracts)

    Runner treats validator as mandatory in v0.
    """

    def validate_input(self, *, role_id: str, artifact: Any) -> None: ...
    def validate_output(self, *, role_id: str, artifact: Any) -> None: ...


RoleFnV0 = Callable[[Any, RunContextV0], Any]


@dataclass(frozen=True)
class RoleCallablesV0:
    """
    Role callables provided to the runner.

    Each role callable MUST be a pure function:
        input_artifact, run_context -> output_artifact | RuntimeErrorV0 (or raise RuntimeErrorV0)

    Notes:
    - Runner does not import role modules directly (no role implementations here).
    - ExecutionRoles stage is represented as a single callable that is responsible for:
        role_orchestrator_output -> task_result_set_v0
      This keeps the runner within runtime responsibilities while preserving pipeline order.
    """

    scope_resolver: RoleFnV0
    intent_interpreter: RoleFnV0
    task_decomposer: RoleFnV0
    role_orchestrator: RoleFnV0
    execution_roles: RoleFnV0
    result_assembler: RoleFnV0


def _extract_trace_id_fail_closed(primary_input: Any) -> str:
    """
    Extract trace_id from the primary input artifact (expected Request Envelope).

    Fail-closed:
    - If trace_id cannot be extracted deterministically, raise ValueError.

    Supported patterns (strict, no heuristics):
    - primary_input['header']['trace_id']
    - primary_input['identity']['trace_id']
    - primary_input['trace_id']
    """
    if isinstance(primary_input, dict):
        if "header" in primary_input and isinstance(primary_input["header"], dict):
            v = primary_input["header"].get("trace_id")
            if isinstance(v, str) and v:
                return v
        if "identity" in primary_input and isinstance(primary_input["identity"], dict):
            v = primary_input["identity"].get("trace_id")
            if isinstance(v, str) and v:
                return v
        v = primary_input.get("trace_id")
        if isinstance(v, str) and v:
            return v
    raise ValueError("Unable to extract trace_id from primary_input (fail-closed)")


def _derive_run_id_v0(determinism_key: str) -> str:
    """
    Deterministic run_id derivation (v0).

    Rule:
    - run_id = "run_" + first 16 hex chars of determinism_key
    """
    if not isinstance(determinism_key, str) or len(determinism_key) < 16:
        raise ValueError("determinism_key must be a hex string with length >= 16")
    return f"run_{determinism_key[:16]}"


def _coerce_role_result_or_raise(result: Any) -> Any:
    """
    Normalize role return semantics.

    v0 accepted patterns:
    - role returns output_artifact (success)
    - role returns RuntimeErrorV0 (failure)
    - role raises RuntimeErrorV0 (failure)
    - role raises Exception (runner wraps into RuntimeErrorV0 using runtime_failure)

    This helper does not wrap generic exceptions; wrapping occurs at call site to preserve role_id.
    """
    if isinstance(result, RuntimeErrorV0):
        raise result
    return result


def run_pipeline_v0(
    *,
    primary_input: Any,
    specs_dir: Path,
    environment: EnvironmentFingerprintV0,
    roles: RoleCallablesV0,
    validator: ArtifactValidatorV0,
    specs: Tuple[ManifestSpecEntryV0, ...],
) -> Tuple[Any, Optional[RuntimeErrorV0], RunManifestV0]:
    """
    Execute the v0 pipeline deterministically.

    Returns:
        (final_output_artifact | None, runtime_error | None, run_manifest_v0)

    Fail-closed:
    - Missing inputs, inability to hash/canonicalize, validation failures, role errors -> failure.
    - On failure, final_output_artifact is None and runtime_error is set.

    Notes:
    - specs must be provided as an immutable tuple of ManifestSpecEntryV0 and must be non-empty.
    - validator is mandatory. If absent/None -> fail-closed.
    """
    if primary_input is None:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="request_envelope_v0",
            determinism_key=_DETERMINISM_KEY_UNAVAILABLE,
            message="primary_input is required",
        )

    if specs_dir is None:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="specs_dir",
            determinism_key=_DETERMINISM_KEY_UNAVAILABLE,
            message="specs_dir is required",
        )

    if environment is None:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="environment_fingerprint_v0",
            determinism_key=_DETERMINISM_KEY_UNAVAILABLE,
            message="environment is required",
        )

    if roles is None:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="role_callables_v0",
            determinism_key=_DETERMINISM_KEY_UNAVAILABLE,
            message="roles are required",
        )

    if validator is None:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="artifact_validator_v0",
            determinism_key=_DETERMINISM_KEY_UNAVAILABLE,
            message="validator is required (fail-closed)",
        )

    if not isinstance(specs, tuple) or len(specs) == 0:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="specs[] (ManifestSpecEntryV0)",
            determinism_key=_DETERMINISM_KEY_UNAVAILABLE,
            message="specs must be a non-empty tuple of ManifestSpecEntryV0",
        )

    # Compute fingerprints deterministically from specs_dir.
    spec_bundle_hash = compute_spec_bundle_hash_v0(specs_dir)
    runtime_policies_fp: PolicyFingerprintV0 = compute_policy_fingerprint_from_specs_v0(specs_dir)
    impl_guidelines_fp: PolicyFingerprintV0 = compute_guidelines_fingerprint_from_specs_v0(specs_dir)

    determinism_key = compute_determinism_key_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=environment,
        runtime_policies=runtime_policies_fp,
        implementation_guidelines=impl_guidelines_fp,
    )

    # trace_id is extracted from primary input (fail-closed).
    try:
        trace_id = _extract_trace_id_fail_closed(primary_input)
    except Exception as e:
        raise invalid_input(
            error_code="GLOBAL_MISSING_INPUT",
            role_id="runtime.runner",
            artifact_expected="request_envelope_v0.trace_id",
            determinism_key=determinism_key,
            message=str(e),
        ) from e

    run_id = _derive_run_id_v0(determinism_key)

    run_context = RunContextV0(
        identity=RunIdentityV0(run_id=run_id, trace_id=trace_id, determinism_key=determinism_key),
        spec_bundle_hash=spec_bundle_hash,
        runtime_policies=runtime_policies_fp,
        implementation_guidelines=impl_guidelines_fp,
        environment=environment,
        seq=0,
    )

    # Primary input hash for manifest inputs.
    try:
        primary_input_hash = artifact_hash(primary_input)
    except Exception as e:
        raise contract_violation(
            error_code="GLOBAL_SCHEMA_INVALID",
            role_id="runtime.runner",
            artifact_expected="request_envelope_v0 (json-serializable)",
            determinism_key=determinism_key,
            message=f"primary_input hashing failed: {e}",
        ) from e

    # Build the initial run manifest.
    manifest = RunManifestV0.from_run_context_v0(
        run_context=run_context,
        primary_input_hash=primary_input_hash,
        input_artifacts=[
            ManifestInputArtifactV0(
                artifact_type="request_envelope",
                artifact_version="request_envelope_v0",
                artifact_hash=primary_input_hash,
            )
        ],
        specs=list(specs),
    )

    current: Any = primary_input

    def _call_role_or_fail_closed(role_id: str, fn: RoleFnV0, input_artifact: Any) -> Any:
        # Pre-validation (fail-closed).
        try:
            validator.validate_input(role_id=role_id, artifact=input_artifact)
        except Exception as e:
            raise contract_violation(
                error_code="GLOBAL_SCHEMA_INVALID",
                role_id=role_id,
                artifact_expected=f"{role_id}.input",
                determinism_key=determinism_key,
                message=f"input validation failed: {e}",
            ) from e

        # Hash input for trace (no user content).
        try:
            in_hash = artifact_hash(input_artifact)
        except Exception as e:
            raise contract_violation(
                error_code="GLOBAL_SCHEMA_INVALID",
                role_id=role_id,
                artifact_expected=f"{role_id}.input (json-serializable)",
                determinism_key=determinism_key,
                message=f"input hashing failed: {e}",
            ) from e

        manifest.record_start(run_context=run_context, role_id=role_id, input_hash=in_hash)

        # Call role (pure function).
        try:
            result = fn(input_artifact, run_context)
            result = _coerce_role_result_or_raise(result)
        except RuntimeErrorV0 as re:
            manifest.record_error(
                run_context=run_context,
                role_id=role_id,
                error_code=re.error_code,
                input_hash=in_hash,
                output_hash=None,
            )
            raise re
        except Exception as e:
            re = runtime_failure(
                error_code="TASK_EXECUTION_FAILED",
                role_id=role_id,
                artifact_expected=f"{role_id}.output",
                determinism_key=determinism_key,
                message=f"role raised unexpected exception: {e}",
            )
            manifest.record_error(
                run_context=run_context,
                role_id=role_id,
                error_code=re.error_code,
                input_hash=in_hash,
                output_hash=None,
            )
            raise re from e

        # Post-validation (fail-closed).
        try:
            validator.validate_output(role_id=role_id, artifact=result)
        except Exception as e:
            re = contract_violation(
                error_code="GLOBAL_SCHEMA_INVALID",
                role_id=role_id,
                artifact_expected=f"{role_id}.output",
                determinism_key=determinism_key,
                message=f"output validation failed: {e}",
            )
            manifest.record_error(
                run_context=run_context,
                role_id=role_id,
                error_code=re.error_code,
                input_hash=in_hash,
                output_hash=None,
            )
            raise re from e

        # Hash output for trace.
        try:
            out_hash = artifact_hash(result)
        except Exception as e:
            re = contract_violation(
                error_code="GLOBAL_SCHEMA_INVALID",
                role_id=role_id,
                artifact_expected=f"{role_id}.output (json-serializable)",
                determinism_key=determinism_key,
                message=f"output hashing failed: {e}",
            )
            manifest.record_error(
                run_context=run_context,
                role_id=role_id,
                error_code=re.error_code,
                input_hash=in_hash,
                output_hash=None,
            )
            raise re from e

        manifest.record_end(
            run_context=run_context,
            role_id=role_id,
            input_hash=in_hash,
            output_hash=out_hash,
        )
        return result

    # Fixed pipeline order per Role Map v0.
    pipeline = (
        ("scope_resolver", roles.scope_resolver),
        ("intent_interpreter", roles.intent_interpreter),
        ("task_decomposer", roles.task_decomposer),
        ("role_orchestrator", roles.role_orchestrator),
        ("execution_roles", roles.execution_roles),
        ("result_assembler", roles.result_assembler),
    )

    final_output: Any = None
    runtime_err: Optional[RuntimeErrorV0] = None

    try:
        for role_id, fn in pipeline:
            current = _call_role_or_fail_closed(role_id, fn, current)
        final_output = current
        try:
            final_hash = artifact_hash(final_output)
        except Exception as e:
            raise contract_violation(
                error_code="GLOBAL_SCHEMA_INVALID",
                role_id="result_assembler",
                artifact_expected="final_response_artifact_v0 (json-serializable)",
                determinism_key=determinism_key,
                message=f"final output hashing failed: {e}",
            ) from e
        manifest.set_final_outcome(status=FinalOutcomeStatus.SUCCESS, final_artifact_hash=final_hash)
        return final_output, None, manifest
    except RuntimeErrorV0 as re:
        runtime_err = re
        manifest.set_final_outcome(status=FinalOutcomeStatus.FAILURE, final_artifact_hash=None)
        return None, runtime_err, manifest
