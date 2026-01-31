from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple

from runtime.determinism import EnvironmentFingerprintV0
from runtime.runner import ArtifactValidatorV0, RoleCallablesV0, run_pipeline_v0
from runtime.run_manifest import ManifestSpecEntryV0


class _NoopValidatorV0:
    """
    Determinism tests focus on runner/manifest stability, not schema correctness.
    Contract tests already enforce schema validation correctness.
    """
    def validate_input(self, *, role_id: str, artifact: Any) -> None:
        return

    def validate_output(self, *, role_id: str, artifact: Any) -> None:
        return


def _make_specs_dir(tmp_path: Path) -> Path:
    """
    Runner determinism tests must provide the policy + guidelines spec files,
    because runner computes their fingerprints from specs_dir (fail-closed).
    """
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    # Required by runtime.determinism.compute_policy_fingerprint_from_specs_v0()
    (specs_dir / "RUNTIME_POLICIES_v0.md").write_text("RUNTIME_POLICIES_v0\n", encoding="utf-8")

    # Required by runtime.determinism.compute_guidelines_fingerprint_from_specs_v0()
    (specs_dir / "IMPLEMENTATION_GUIDELINES_v0.md").write_text("IMPLEMENTATION_GUIDELINES_v0\n", encoding="utf-8")

    # Optional for bundle hash entropy (fine to keep)
    (specs_dir / "SPEC_A.md").write_text("SPEC_A v0\nline2\n", encoding="utf-8")
    (specs_dir / "SPEC_B.md").write_text("SPEC_B v0\n", encoding="utf-8")

    return specs_dir



def _roles_deterministic() -> RoleCallablesV0:
    # Each stage produces a deterministic, json-serializable mapping.
    def scope_resolver(inp: Any, _ctx: Any) -> Any:
        return {"stage": "scope_resolver", "in": inp}

    def intent_interpreter(inp: Any, _ctx: Any) -> Any:
        return {"stage": "intent_interpreter", "in": inp}

    def task_decomposer(inp: Any, _ctx: Any) -> Any:
        return {"stage": "task_decomposer", "in": inp}

    def role_orchestrator(inp: Any, _ctx: Any) -> Any:
        return {"stage": "role_orchestrator", "in": inp}

    def execution_roles(inp: Any, _ctx: Any) -> Any:
        return {"stage": "execution_roles", "in": inp}

    def result_assembler(inp: Any, _ctx: Any) -> Any:
        return {"stage": "result_assembler", "in": inp}

    return RoleCallablesV0(
        scope_resolver=scope_resolver,
        intent_interpreter=intent_interpreter,
        task_decomposer=task_decomposer,
        role_orchestrator=role_orchestrator,
        execution_roles=execution_roles,
        result_assembler=result_assembler,
    )


def _specs_minimal() -> Tuple[ManifestSpecEntryV0, ...]:
    # Runner requires non-empty tuple.
    # These are only recorded into the manifest; spec bundle hash is derived from specs_dir content.
    return (
        ManifestSpecEntryV0(spec_name="SPEC_A", spec_version="v0", spec_hash="hash_a"),
    )


def test_runner_produces_identical_manifest_for_identical_inputs(tmp_path: Path) -> None:
    specs_dir = _make_specs_dir(tmp_path)

    env = EnvironmentFingerprintV0(
        runtime_version="runtime_v0",
        model_id="model_test",
        model_version="model_test_v1",
        tokenizer_version="tok_v1",
    )

    primary_input = {
        # Must have trace_id extractable by runner._extract_trace_id_fail_closed()
        "header": {"trace_id": "trace_123"},
        # Other fields irrelevant for determinism test; hashing is deterministic anyway.
        "payload_isolation": {"baseline_norm": "X", "dialogue_context_included": False},
        "intent": {"intent": "TEST"},
        "maturity_gate": {"maturity": "MATURE", "reason_code": "OK", "recommended_next": "route"},
        "consistency": {"contradictions_detected": False},
    }

    roles = _roles_deterministic()
    validator: ArtifactValidatorV0 = _NoopValidatorV0()
    specs = _specs_minimal()

    out1, err1, m1 = run_pipeline_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        roles=roles,
        validator=validator,
        specs=specs,
    )
    out2, err2, m2 = run_pipeline_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        roles=roles,
        validator=validator,
        specs=specs,
    )

    assert err1 is None and err2 is None
    assert out1 == out2

    # Strongest check: serialized manifest dict must match exactly.
    assert m1.to_dict() == m2.to_dict()

    # Additionally: seq ordering must be deterministic and monotonic.
    trace1 = m1.to_dict()["run_manifest"]["execution_trace"]
    seqs = [e["seq"] for e in trace1]
    assert seqs == sorted(seqs)
    assert len(seqs) == 12  # 6 roles * (START+END)


def test_runner_manifest_changes_when_primary_input_changes(tmp_path: Path) -> None:
    specs_dir = _make_specs_dir(tmp_path)

    env = EnvironmentFingerprintV0(
        runtime_version="runtime_v0",
        model_id="model_test",
        model_version="model_test_v1",
        tokenizer_version="tok_v1",
    )

    roles = _roles_deterministic()
    validator: ArtifactValidatorV0 = _NoopValidatorV0()
    specs = _specs_minimal()

    a = {
        "header": {"trace_id": "trace_123"},
        "payload_isolation": {"baseline_norm": "X", "dialogue_context_included": False},
    }
    b = {
        "header": {"trace_id": "trace_123"},
        "payload_isolation": {"baseline_norm": "Y", "dialogue_context_included": False},
    }

    _, err1, m1 = run_pipeline_v0(
        primary_input=a,
        specs_dir=specs_dir,
        environment=env,
        roles=roles,
        validator=validator,
        specs=specs,
    )
    _, err2, m2 = run_pipeline_v0(
        primary_input=b,
        specs_dir=specs_dir,
        environment=env,
        roles=roles,
        validator=validator,
        specs=specs,
    )

    assert err1 is None and err2 is None
    assert m1.to_dict()["run_manifest"]["run_identity"]["determinism_key"] != m2.to_dict()["run_manifest"]["run_identity"]["determinism_key"]
