from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


MARKERS = (
    "=== output_summary ===",
    "=== output ===",
    "=== runtime_error ===",
    "=== run_manifest ===",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "extensions" / "profiles"


def _extract_json_block(stdout: str, marker: str) -> Any:
    idx = stdout.find(marker)
    if idx < 0:
        raise AssertionError(f"Marker not found: {marker}")

    start = idx + len(marker)
    while start < len(stdout) and stdout[start] in " \r\n\t":
        start += 1

    next_positions = []
    for m in MARKERS:
        if m == marker:
            continue
        p = stdout.find(m, start)
        if p >= 0:
            next_positions.append(p)
    end = min(next_positions) if next_positions else len(stdout)

    blob = stdout[start:end].strip()
    return json.loads(blob)


def _run_cli(text: str, *, profile: str, env_overrides: Dict[str, str] | None = None) -> Tuple[dict, dict, Any, dict]:
    cmd = [sys.executable, "-m", "apps.front_cli", "--profile", profile, "--text", text]
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)

    if res.returncode != 0:
        raise AssertionError(
            f"CLI exit={res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\n"
        )

    summary = _extract_json_block(res.stdout, "=== output_summary ===")
    output = _extract_json_block(res.stdout, "=== output ===")
    runtime_error = _extract_json_block(res.stdout, "=== runtime_error ===")
    run_manifest_wrapper = _extract_json_block(res.stdout, "=== run_manifest ===")
    manifest = run_manifest_wrapper["run_manifest"]
    return summary, output, runtime_error, manifest


def _ensure_profile_file(name: str, json_text: str) -> None:
    """
    Create/overwrite profile file with utf-8 (no BOM) deterministically for tests.
    """
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{name}.json"
    path.write_text(json_text, encoding="utf-8")


def test_profile_rolepack_selects_v1_tz_without_env() -> None:
    _ensure_profile_file("tz_cli_test_v1_tz", '{\n  "rolepack": "v1_tz"\n}\n')

    summary, output, runtime_error, manifest = _run_cli(
        "hello",
        profile="tz_cli_test_v1_tz",
        env_overrides={"ORCHESTRA_ROLEPACK": ""},  # ensure not set effectively
    )

    assert runtime_error is None
    assert manifest["final_outcome"]["status"] == "success"
    assert output.get("schema_version") == "final_response_artifact_v0"


def test_env_overrides_profile() -> None:
    # profile requests v1_tz, but env forces deterministic
    _ensure_profile_file("tz_cli_test_v1_tz", '{\n  "rolepack": "v1_tz"\n}\n')

    summary, output, runtime_error, manifest = _run_cli(
        "hello",
        profile="tz_cli_test_v1_tz",
        env_overrides={"ORCHESTRA_ROLEPACK": "deterministic"},
    )

    assert runtime_error is None
    assert manifest["final_outcome"]["status"] == "success"

    # deterministic rolepack produces nested stage output (not final_response_artifact_v0)
    assert output.get("schema_version") != "final_response_artifact_v0"
    assert output.get("stage") == "result_assembler"
