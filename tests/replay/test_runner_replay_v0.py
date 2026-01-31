from __future__ import annotations

import json
from pathlib import Path

from runtime.determinism import EnvironmentFingerprintV0
from runtime.runner import run_pipeline_v0

from tests.determinism.test_runner_manifest_determinism_v0 import (
    _NoopValidatorV0,
    _make_specs_dir,
    _roles_deterministic,
    _specs_minimal,
)


def test_runner_replay_v0(tmp_path: Path) -> None:
    specs_dir = _make_specs_dir(tmp_path)

    env = EnvironmentFingerprintV0(
        runtime_version="runtime_v0",
        model_id="model_test",
        model_version="model_test_v1",
        tokenizer_version="tok_v1",
    )

    primary_input = json.loads(
        Path("tests/replay/data/replay_input_v0.json").read_text(encoding="utf-8")
    )

    out1, err1, m1 = run_pipeline_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        roles=_roles_deterministic(),
        validator=_NoopValidatorV0(),
        specs=_specs_minimal(),
    )

    out2, err2, m2 = run_pipeline_v0(
        primary_input=primary_input,
        specs_dir=specs_dir,
        environment=env,
        roles=_roles_deterministic(),
        validator=_NoopValidatorV0(),
        specs=_specs_minimal(),
    )

    assert err1 is None
    assert err2 is None
    assert out1 == out2
    assert m1.to_dict() == m2.to_dict()

    golden = json.loads(
        Path("tests/replay/data/replay_manifest_v0.json").read_text(encoding="utf-8")
    )

    assert m1.to_dict() == golden
