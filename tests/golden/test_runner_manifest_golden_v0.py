from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple

from runtime.determinism import EnvironmentFingerprintV0
from runtime.runner import run_pipeline_v0, ArtifactValidatorV0, RoleCallablesV0
from runtime.run_manifest import ManifestSpecEntryV0


class _NoopValidatorV0:
    def validate_input(self, *, role_id: str, artifact: Any) -> None:
        return

    def validate_output(self, *, role_id: str, artifact: Any) -> None:
        return


def _roles_deterministic() -> RoleCallablesV0:
    # минимальная “протяжка” без логики: input -> input
    def passthrough(x: Any, _ctx: Any) -> Any:
        return x

    return RoleCallablesV0(
        scope_resolver=passthrough,
        intent_interpreter=passthrough,
        task_decomposer=passthrough,
        role_orchestrator=passthrough,
        execution_roles=passthrough,
        result_assembler=passthrough,
    )


def _specs_minimal() -> Tuple[ManifestSpecEntryV0, ...]:
    # В golden тесте specs в манифесте должны быть детерминированы.
    return (
        ManifestSpecEntryV0(spec_name="FRONT_MANAGER_SPEC.md", spec_version="v0", spec_hash="dummy"),
    )


def _make_specs_dir(tmp_path: Path) -> Path:
    # ВАЖНО: runner/determinism ожидает эти файлы по именам.
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    (specs_dir / "RUNTIME_POLICIES_v0.md").write_text("runtime_policies_v0", encoding="utf-8")
    (specs_dir / "IMPLEMENTATION_GUIDELINES_v0.md").write_text("implementation_guidelines_v0", encoding="utf-8")

    # spec bundle hash обычно считает всё содержимое specs_dir — этого достаточно.
    return specs_dir


def test_runner_manifest_matches_golden(tmp_path: Path) -> None:
    specs_dir = _make_specs_dir(tmp_path)

    env = EnvironmentFingerprintV0(
        runtime_version="runtime_v0",
        model_id="model_test",
        model_version="model_test_v1",
        tokenizer_version="tok_v1",
    )

    primary_input = {
        "schema_version": "request_envelope_v0",
        "header": {
            "trace_id": "trace_123",
            "envelope_id": "env_1",
            "req_id": "req_1",
            "created_at": "2026-01-01T00:00:00Z",
            "source": "user",
            "mode": "platform",
        },
        "payload_isolation": {"baseline_norm": "X", "dialogue_context_included": False},
        "intent": {"intent": "TEST"},
        "maturity_gate": {"maturity": "MATURE", "reason_code": "OK", "recommended_next": "route"},
        "consistency": {"contradictions_detected": False},
    }

    out, err, manifest = run_pipeline_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        roles=_roles_deterministic(),
        validator=_NoopValidatorV0(),  # type: ignore[assignment]
        specs=_specs_minimal(),
    )

    assert err is None
    assert out is not None

    got = manifest.to_dict()

    golden_path = Path("tests/golden/data/runner_manifest_golden_v0.json")
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert got == expected


