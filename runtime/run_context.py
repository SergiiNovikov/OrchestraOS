"""
Implements: RUN_MANIFEST_SCHEMA_v0.md, section 3 (run_identity, execution_trace.seq)
Implements: RUNTIME_POLICIES_v0.md, sections 3, 5, 9 (trace propagation, determinism_key, deterministic ordering)
Implements: IMPLEMENTATION_GUIDELINES_v0.md, sections 4, 7 (determinism_key usage, trace format)

Scope:
- Define RunContextV0: minimal read-only runtime context propagated across a run.
- Provide deterministic sequencing for execution_trace events (seq counter).
- RunContext MUST NOT contain user content; only identifiers and hashes/fingerprints.
"""

from __future__ import annotations

from dataclasses import dataclass

from runtime.determinism import EnvironmentFingerprintV0, PolicyFingerprintV0


@dataclass(frozen=True)
class RunIdentityV0:
    """
    Run identity tuple.

    Aligns with RUN_MANIFEST_SCHEMA_v0.md run_identity:
    - run_id
    - trace_id
    - determinism_key
    """

    run_id: str
    trace_id: str
    determinism_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(self.trace_id, str) or not self.trace_id:
            raise ValueError("trace_id must be a non-empty string")
        if not isinstance(self.determinism_key, str) or not self.determinism_key:
            raise ValueError("determinism_key must be a non-empty string")


@dataclass
class RunContextV0:
    """
    Mutable runtime context for a single run.

    Read-only for roles by convention (roles must treat run_context as read-only),
    but runtime infrastructure may mutate seq deterministically.

    Fields:
    - identity: RunIdentityV0
    - spec_bundle_hash: hash of specs/ mirror bundle
    - runtime_policies: PolicyFingerprintV0 (version+hash)
    - implementation_guidelines: PolicyFingerprintV0 (version+hash)
    - environment: EnvironmentFingerprintV0 (runtime/model/tokenizer/python)
    - seq: deterministic event sequence counter (monotonic within run)
    """

    identity: RunIdentityV0
    spec_bundle_hash: str
    runtime_policies: PolicyFingerprintV0
    implementation_guidelines: PolicyFingerprintV0
    environment: EnvironmentFingerprintV0
    seq: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.spec_bundle_hash, str) or not self.spec_bundle_hash:
            raise ValueError("spec_bundle_hash must be a non-empty string")
        if not isinstance(self.runtime_policies, PolicyFingerprintV0):
            raise TypeError("runtime_policies must be PolicyFingerprintV0")
        if not isinstance(self.implementation_guidelines, PolicyFingerprintV0):
            raise TypeError("implementation_guidelines must be PolicyFingerprintV0")
        if not isinstance(self.environment, EnvironmentFingerprintV0):
            raise TypeError("environment must be EnvironmentFingerprintV0")
        if not isinstance(self.seq, int) or self.seq < 0:
            raise ValueError("seq must be a non-negative integer")

    def next_seq(self) -> int:
        """
        Increment and return the next deterministic sequence number.

        Determinism requirement:
        - seq increments are performed only by runtime in a fixed execution order.
        - seq values MUST NOT depend on timestamps, concurrency, or external factors.

        Returns:
            int: next sequence number (starting from 1).
        """
        self.seq += 1
        return self.seq

    @property
    def run_id(self) -> str:
        return self.identity.run_id

    @property
    def trace_id(self) -> str:
        return self.identity.trace_id

    @property
    def determinism_key(self) -> str:
        return self.identity.determinism_key

