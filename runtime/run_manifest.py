"""
Implements: RUN_MANIFEST_SCHEMA_v0.md, sections 2, 3, 4, 5
Implements: RUNTIME_POLICIES_v0.md, sections 3, 9, 11 (deterministic trace ordering, auditability, replay)
Implements: IMPLEMENTATION_GUIDELINES_v0.md, sections 7, 9 (trace format, manifest usage)

Scope:
- Define the machine-readable Run Manifest schema v0 as dataclasses.
- Provide deterministic, fail-closed helpers to build and record execution trace events.
- Enforce the invariant: Run Manifest MUST NOT contain user content in open form (hashes only).

Notes:
- This module is runtime infrastructure (not a role).
- It must remain deterministic and fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from runtime.run_context import RunContextV0


class TraceEventType(str, Enum):
    """Implements: RUN_MANIFEST_SCHEMA_v0.md, execution_trace.event_type."""
    START = "START"
    END = "END"
    ERROR = "ERROR"


class FinalOutcomeStatus(str, Enum):
    """Implements: RUN_MANIFEST_SCHEMA_v0.md, final_outcome.status."""
    SUCCESS = "success"
    FAILURE = "failure"


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_non_empty_str(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string when provided")
    return value


def _require_non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class ManifestInputArtifactV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, inputs.artifacts[].
    Stores only identifiers and hashes (no user content).
    """
    artifact_type: str
    artifact_version: str
    artifact_hash: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.artifact_type, "artifact_type")
        _require_non_empty_str(self.artifact_version, "artifact_version")
        _require_non_empty_str(self.artifact_hash, "artifact_hash")


@dataclass(frozen=True)
class ManifestSpecEntryV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, specs[].
    """
    spec_name: str
    spec_version: str
    spec_hash: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.spec_name, "spec_name")
        _require_non_empty_str(self.spec_version, "spec_version")
        _require_non_empty_str(self.spec_hash, "spec_hash")


@dataclass(frozen=True)
class ManifestRunIdentityV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, run_identity.
    """
    run_id: str
    trace_id: str
    determinism_key: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.run_id, "run_id")
        _require_non_empty_str(self.trace_id, "trace_id")
        _require_non_empty_str(self.determinism_key, "determinism_key")


@dataclass(frozen=True)
class ManifestInputsV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, inputs.
    """
    primary_input_hash: str
    artifacts: List[ManifestInputArtifactV0] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.primary_input_hash, "primary_input_hash")
        if not isinstance(self.artifacts, list):
            raise TypeError("artifacts must be a list")
        for a in self.artifacts:
            if not isinstance(a, ManifestInputArtifactV0):
                raise TypeError("artifacts must contain ManifestInputArtifactV0 items")


@dataclass(frozen=True)
class ManifestRuntimePoliciesV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, runtime_policies.
    """
    policy_version: str
    policy_hash: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.policy_version, "policy_version")
        _require_non_empty_str(self.policy_hash, "policy_hash")


@dataclass(frozen=True)
class ManifestImplementationGuidelinesV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, implementation_guidelines.
    """
    guidelines_version: str
    guidelines_hash: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.guidelines_version, "guidelines_version")
        _require_non_empty_str(self.guidelines_hash, "guidelines_hash")


@dataclass(frozen=True)
class ManifestEnvironmentV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, environment.

    IMPORTANT:
    - Must not include user content.
    - Must include only fields specified by schema v0.
    """
    runtime_version: str
    model_id: str
    model_version: str
    tokenizer_version: Optional[str] = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.runtime_version, "runtime_version")
        _require_non_empty_str(self.model_id, "model_id")
        _require_non_empty_str(self.model_version, "model_version")
        _optional_non_empty_str(self.tokenizer_version, "tokenizer_version")


@dataclass(frozen=True)
class ManifestTraceEventV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, execution_trace[].
    """
    seq: int
    role_id: str
    event_type: TraceEventType
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    error_code: Optional[str] = None

    def __post_init__(self) -> None:
        _require_non_negative_int(self.seq, "seq")
        _require_non_empty_str(self.role_id, "role_id")
        if not isinstance(self.event_type, TraceEventType):
            raise TypeError("event_type must be TraceEventType")

        _optional_non_empty_str(self.input_hash, "input_hash")
        _optional_non_empty_str(self.output_hash, "output_hash")
        _optional_non_empty_str(self.error_code, "error_code")

        # Schema intent: error_code only meaningful for ERROR events (fail-closed sanity check).
        if self.event_type == TraceEventType.ERROR and self.error_code is None:
            raise ValueError("error_code is required when event_type == ERROR")
        if self.event_type != TraceEventType.ERROR and self.error_code is not None:
            raise ValueError("error_code must be omitted unless event_type == ERROR")


@dataclass(frozen=True)
class ManifestFinalOutcomeV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, final_outcome.
    """
    status: FinalOutcomeStatus
    final_artifact_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, FinalOutcomeStatus):
            raise TypeError("status must be FinalOutcomeStatus")
        _optional_non_empty_str(self.final_artifact_hash, "final_artifact_hash")


@dataclass
class RunManifestV0:
    """
    Implements: RUN_MANIFEST_SCHEMA_v0.md, run_manifest (root).

    Note:
    - Mutable only to append deterministic execution_trace and to set final_outcome.
    - MUST NOT contain user content in open form (hashes only).
    """

    schema_version: str
    run_identity: ManifestRunIdentityV0
    inputs: ManifestInputsV0
    specs: List[ManifestSpecEntryV0]
    runtime_policies: ManifestRuntimePoliciesV0
    implementation_guidelines: ManifestImplementationGuidelinesV0
    environment: ManifestEnvironmentV0
    execution_trace: List[ManifestTraceEventV0] = field(default_factory=list)
    final_outcome: ManifestFinalOutcomeV0 = field(
        default_factory=lambda: ManifestFinalOutcomeV0(status=FinalOutcomeStatus.FAILURE)
    )

    def __post_init__(self) -> None:
        _require_non_empty_str(self.schema_version, "schema_version")
        if self.schema_version != "run_manifest_v0":
            raise ValueError("schema_version must be 'run_manifest_v0'")

        if not isinstance(self.run_identity, ManifestRunIdentityV0):
            raise TypeError("run_identity must be ManifestRunIdentityV0")
        if not isinstance(self.inputs, ManifestInputsV0):
            raise TypeError("inputs must be ManifestInputsV0")

        if not isinstance(self.specs, list) or not self.specs:
            raise ValueError("specs must be a non-empty list of ManifestSpecEntryV0")
        for s in self.specs:
            if not isinstance(s, ManifestSpecEntryV0):
                raise TypeError("specs must contain ManifestSpecEntryV0 items")

        if not isinstance(self.runtime_policies, ManifestRuntimePoliciesV0):
            raise TypeError("runtime_policies must be ManifestRuntimePoliciesV0")
        if not isinstance(self.implementation_guidelines, ManifestImplementationGuidelinesV0):
            raise TypeError("implementation_guidelines must be ManifestImplementationGuidelinesV0")
        if not isinstance(self.environment, ManifestEnvironmentV0):
            raise TypeError("environment must be ManifestEnvironmentV0")

        if not isinstance(self.execution_trace, list):
            raise TypeError("execution_trace must be a list")
        for e in self.execution_trace:
            if not isinstance(e, ManifestTraceEventV0):
                raise TypeError("execution_trace must contain ManifestTraceEventV0 items")

        if not isinstance(self.final_outcome, ManifestFinalOutcomeV0):
            raise TypeError("final_outcome must be ManifestFinalOutcomeV0")

    @staticmethod
    def from_run_context_v0(
        *,
        run_context: RunContextV0,
        primary_input_hash: str,
        input_artifacts: Optional[List[ManifestInputArtifactV0]] = None,
        specs: List[ManifestSpecEntryV0],
    ) -> "RunManifestV0":
        """
        Construct a new RunManifestV0 from RunContextV0.

        Args:
            run_context: runtime context containing run_identity and fingerprints.
            primary_input_hash: hash of the primary input (no content).
            input_artifacts: optional list of additional input artifact hashes.
            specs: non-empty list of spec entries (spec_name/spec_version/spec_hash).

        Returns:
            RunManifestV0
        """
        if not isinstance(run_context, RunContextV0):
            raise TypeError("run_context must be RunContextV0")
        _require_non_empty_str(primary_input_hash, "primary_input_hash")
        if input_artifacts is None:
            input_artifacts = []
        if not isinstance(input_artifacts, list):
            raise TypeError("input_artifacts must be a list when provided")
        for a in input_artifacts:
            if not isinstance(a, ManifestInputArtifactV0):
                raise TypeError("input_artifacts must contain ManifestInputArtifactV0 items")
        if not isinstance(specs, list) or not specs:
            raise ValueError("specs must be a non-empty list of ManifestSpecEntryV0")
        for s in specs:
            if not isinstance(s, ManifestSpecEntryV0):
                raise TypeError("specs must contain ManifestSpecEntryV0 items")

        rid = ManifestRunIdentityV0(
            run_id=run_context.run_id,
            trace_id=run_context.trace_id,
            determinism_key=run_context.determinism_key,
        )

        inp = ManifestInputsV0(primary_input_hash=primary_input_hash, artifacts=input_artifacts)

        rp = ManifestRuntimePoliciesV0(
            policy_version=run_context.runtime_policies.version,
            policy_hash=run_context.runtime_policies.content_hash,
        )
        ig = ManifestImplementationGuidelinesV0(
            guidelines_version=run_context.implementation_guidelines.version,
            guidelines_hash=run_context.implementation_guidelines.content_hash,
        )

        env = ManifestEnvironmentV0(
            runtime_version=run_context.environment.runtime_version,
            model_id=run_context.environment.model_id,
            model_version=run_context.environment.model_version,
            tokenizer_version=run_context.environment.tokenizer_version,
        )

        # final_outcome is provided by default_factory (single source of default truth).
        return RunManifestV0(
            schema_version="run_manifest_v0",
            run_identity=rid,
            inputs=inp,
            specs=specs,
            runtime_policies=rp,
            implementation_guidelines=ig,
            environment=env,
            execution_trace=[],
        )

    def record_start(self, *, run_context: RunContextV0, role_id: str, input_hash: Optional[str] = None) -> None:
        """
        Append a START trace event with deterministic seq from run_context.
        """
        if not isinstance(run_context, RunContextV0):
            raise TypeError("run_context must be RunContextV0")
        _require_non_empty_str(role_id, "role_id")
        _optional_non_empty_str(input_hash, "input_hash")

        ev = ManifestTraceEventV0(
            seq=run_context.next_seq(),
            role_id=role_id,
            event_type=TraceEventType.START,
            input_hash=input_hash,
            output_hash=None,
            error_code=None,
        )
        self.execution_trace.append(ev)

    def record_end(
        self,
        *,
        run_context: RunContextV0,
        role_id: str,
        input_hash: Optional[str] = None,
        output_hash: Optional[str] = None,
    ) -> None:
        """
        Append an END trace event with deterministic seq from run_context.
        """
        if not isinstance(run_context, RunContextV0):
            raise TypeError("run_context must be RunContextV0")
        _require_non_empty_str(role_id, "role_id")
        _optional_non_empty_str(input_hash, "input_hash")
        _optional_non_empty_str(output_hash, "output_hash")

        ev = ManifestTraceEventV0(
            seq=run_context.next_seq(),
            role_id=role_id,
            event_type=TraceEventType.END,
            input_hash=input_hash,
            output_hash=output_hash,
            error_code=None,
        )
        self.execution_trace.append(ev)

    def record_error(
        self,
        *,
        run_context: RunContextV0,
        role_id: str,
        error_code: str,
        input_hash: Optional[str] = None,
        output_hash: Optional[str] = None,
    ) -> None:
        """
        Append an ERROR trace event with deterministic seq from run_context.
        """
        if not isinstance(run_context, RunContextV0):
            raise TypeError("run_context must be RunContextV0")
        _require_non_empty_str(role_id, "role_id")
        _require_non_empty_str(error_code, "error_code")
        _optional_non_empty_str(input_hash, "input_hash")
        _optional_non_empty_str(output_hash, "output_hash")

        ev = ManifestTraceEventV0(
            seq=run_context.next_seq(),
            role_id=role_id,
            event_type=TraceEventType.ERROR,
            input_hash=input_hash,
            output_hash=output_hash,
            error_code=error_code,
        )
        self.execution_trace.append(ev)

    def set_final_outcome(self, *, status: FinalOutcomeStatus, final_artifact_hash: Optional[str] = None) -> None:
        """
        Set final outcome.

        Fail-closed:
        - status must be FinalOutcomeStatus.
        - final_artifact_hash must be non-empty string if provided.
        """
        if not isinstance(status, FinalOutcomeStatus):
            raise TypeError("status must be FinalOutcomeStatus")
        _optional_non_empty_str(final_artifact_hash, "final_artifact_hash")

        self.final_outcome = ManifestFinalOutcomeV0(status=status, final_artifact_hash=final_artifact_hash)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize RunManifestV0 into a plain dict aligned with RUN_MANIFEST_SCHEMA_v0.md.

        NOTE:
        - This is a runtime serialization helper.
        - MUST remain deterministic given deterministic field values.
        - MUST NOT introduce user content.
        """
        return {
            "run_manifest": {
                "schema_version": self.schema_version,
                "run_identity": {
                    "run_id": self.run_identity.run_id,
                    "trace_id": self.run_identity.trace_id,
                    "determinism_key": self.run_identity.determinism_key,
                },
                "inputs": {
                    "primary_input_hash": self.inputs.primary_input_hash,
                    "artifacts": [
                        {
                            "artifact_type": a.artifact_type,
                            "artifact_version": a.artifact_version,
                            "artifact_hash": a.artifact_hash,
                        }
                        for a in self.inputs.artifacts
                    ],
                },
                "specs": [
                    {
                        "spec_name": s.spec_name,
                        "spec_version": s.spec_version,
                        "spec_hash": s.spec_hash,
                    }
                    for s in self.specs
                ],
                "runtime_policies": {
                    "policy_version": self.runtime_policies.policy_version,
                    "policy_hash": self.runtime_policies.policy_hash,
                },
                "implementation_guidelines": {
                    "guidelines_version": self.implementation_guidelines.guidelines_version,
                    "guidelines_hash": self.implementation_guidelines.guidelines_hash,
                },
                "environment": {
                    "runtime_version": self.environment.runtime_version,
                    "model_id": self.environment.model_id,
                    "model_version": self.environment.model_version,
                    "tokenizer_version": self.environment.tokenizer_version,
                },
                "execution_trace": [
                    {
                        "seq": e.seq,
                        "role_id": e.role_id,
                        "event_type": e.event_type.value,
                        "input_hash": e.input_hash,
                        "output_hash": e.output_hash,
                        "error_code": e.error_code,
                    }
                    for e in self.execution_trace
                ],
                "final_outcome": {
                    "status": self.final_outcome.status.value,
                    "final_artifact_hash": self.final_outcome.final_artifact_hash,
                },
            }
        }
