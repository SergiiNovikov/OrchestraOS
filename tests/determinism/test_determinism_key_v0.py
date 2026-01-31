from __future__ import annotations

from pathlib import Path

from runtime.determinism import (
    EnvironmentFingerprintV0,
    PolicyFingerprintV0,
    compute_determinism_key_v0,
)


def _make_specs_dir(tmp_path: Path) -> Path:
    """
    Determinism tests MUST NOT depend on repo files.
    We create a minimal specs_dir with deterministic contents.
    """
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "SPEC_A.md").write_text("SPEC_A v0\nline2\n", encoding="utf-8")
    (specs_dir / "SPEC_B.md").write_text("SPEC_B v0\n", encoding="utf-8")
    return specs_dir


def test_compute_determinism_key_is_stable_for_same_inputs(tmp_path: Path) -> None:
    specs_dir = _make_specs_dir(tmp_path)

    primary_input = {
        "schema_version": "request_envelope_v0",
        "header": {"trace_id": "trace_123", "mode": "platform"},
        "payload_isolation": {"baseline_norm": "x", "dialogue_context_included": False},
        "intent": {"intent": "TEST"},
        "maturity_gate": {"maturity": "MATURE", "reason_code": "OK", "recommended_next": "route"},
        "consistency": {"contradictions_detected": False},
    }

    env = EnvironmentFingerprintV0(
        runtime_version="runtime_v0",
        model_id="model_test",
        model_version="model_test_v1",
        tokenizer_version="tok_v1",
    )

    rp = PolicyFingerprintV0(version="RUNTIME_POLICIES_v0", content_hash="rp_hash")
    ig = PolicyFingerprintV0(version="IMPLEMENTATION_GUIDELINES_v0", content_hash="ig_hash")

    k1 = compute_determinism_key_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        runtime_policies=rp,
        implementation_guidelines=ig,
    )
    k2 = compute_determinism_key_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        runtime_policies=rp,
        implementation_guidelines=ig,
    )

    assert isinstance(k1, str) and k1 != ""
    assert k1 == k2


def test_compute_determinism_key_changes_when_primary_input_changes(tmp_path: Path) -> None:
    specs_dir = _make_specs_dir(tmp_path)

    env = EnvironmentFingerprintV0(
        runtime_version="runtime_v0",
        model_id="model_test",
        model_version="model_test_v1",
        tokenizer_version="tok_v1",
    )
    rp = PolicyFingerprintV0(version="RUNTIME_POLICIES_v0", content_hash="rp_hash")
    ig = PolicyFingerprintV0(version="IMPLEMENTATION_GUIDELINES_v0", content_hash="ig_hash")

    a = {"x": 1}
    b = {"x": 2}

    k1 = compute_determinism_key_v0(
        primary_input=a,
        specs_dir=specs_dir,
        environment=env,
        runtime_policies=rp,
        implementation_guidelines=ig,
    )
    k2 = compute_determinism_key_v0(
        primary_input=b,
        specs_dir=specs_dir,
        environment=env,
        runtime_policies=rp,
        implementation_guidelines=ig,
    )

    assert k1 != k2
