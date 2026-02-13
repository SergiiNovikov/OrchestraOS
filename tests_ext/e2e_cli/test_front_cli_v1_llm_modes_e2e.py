from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest


MARKERS = (
    "=== output_summary ===",
    "=== output ===",
    "=== runtime_error ===",
    "=== run_manifest ===",
)


def _extract_json_block(stdout: str, marker: str) -> Any:
    if not isinstance(stdout, str):
        raise AssertionError(f"CLI stdout must be str, got: {type(stdout)}")

    idx = stdout.find(marker)
    if idx < 0:
        raise AssertionError(f"Marker not found: {marker}\nSTDOUT:\n{stdout}")

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
    if not blob:
        return None
    return json.loads(blob)


def _run_cli(
    text: str,
    *,
    env_overrides: Dict[str, str] | None = None,
    expect_success: bool,
) -> Tuple[int, str, str]:
    cmd = [sys.executable, "-m", "apps.front_cli", "--text", text]
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    # Windows-friendly decode/encode handling
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )

    if expect_success and res.returncode != 0:
        raise AssertionError(
            f"CLI exit={res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\n"
        )

    if (not expect_success) and res.returncode == 0:
        raise AssertionError(
            f"Expected CLI to fail (fail-closed), but exit=0\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\n"
        )

    return res.returncode, res.stdout, res.stderr


def _parse_success_blocks(stdout: str) -> Tuple[dict, dict, Any, dict]:
    summary = _extract_json_block(stdout, "=== output_summary ===")
    output = _extract_json_block(stdout, "=== output ===")
    runtime_error = _extract_json_block(stdout, "=== runtime_error ===")
    run_manifest_wrapper = _extract_json_block(stdout, "=== run_manifest ===")

    if not isinstance(run_manifest_wrapper, dict) or "run_manifest" not in run_manifest_wrapper:
        raise AssertionError(f"Missing run_manifest wrapper: {run_manifest_wrapper!r}")

    manifest = run_manifest_wrapper["run_manifest"]
    if not isinstance(summary, dict) or not isinstance(output, dict) or not isinstance(manifest, dict):
        raise AssertionError(
            f"Unexpected types: summary={type(summary)} output={type(output)} manifest={type(manifest)}"
        )
    return summary, output, runtime_error, manifest


def _assert_success_and_schema_valid(summary: dict, output: dict, runtime_error: Any, manifest: dict) -> None:
    assert runtime_error is None

    final = manifest.get("final_outcome")
    assert isinstance(final, dict)
    assert final.get("status") == "success"

    schema_version = output.get("schema_version")
    assert isinstance(schema_version, str) and schema_version

    from validation.schemas import validate_artifact_v0

    validate_artifact_v0(artifact=output, expected_schema_version=schema_version)


def test_v1_llm_mode_off_determinism_n3_e2e(tmp_path: Path) -> None:
    env = {
        "ORCHESTRA_ROLEPACK": "v1_llm",
        "LLM_MODE": "off",
        "LLM_CACHE_DIR": str(tmp_path),
    }

    runs = []
    for _ in range(3):
        _, stdout, _ = _run_cli("hello", env_overrides=env, expect_success=True)
        summary, output, runtime_error, manifest = _parse_success_blocks(stdout)
        _assert_success_and_schema_valid(summary, output, runtime_error, manifest)
        runs.append((summary, output, runtime_error, manifest))

    assert runs[0] == runs[1] == runs[2]


def test_v1_llm_mode_replay_cache_miss_fail_closed_e2e(tmp_path: Path) -> None:
    env = {
        "ORCHESTRA_ROLEPACK": "v1_llm",
        "LLM_MODE": "replay",
        "LLM_CACHE_DIR": str(tmp_path),
    }

    # replay with empty cache must fail-closed at CLI level
    _run_cli("hello", env_overrides=env, expect_success=False)


def test_v1_llm_mode_record_stub_then_replay_hit_e2e(tmp_path: Path) -> None:
    # 1) record (stub) should succeed and write cache
    env_record = {
        "ORCHESTRA_ROLEPACK": "v1_llm",
        "LLM_MODE": "record",
        "LLM_PROVIDER": "stub",
        "LLM_CACHE_DIR": str(tmp_path),
    }
    _, stdout1, _ = _run_cli("hello", env_overrides=env_record, expect_success=True)
    s1, o1, e1, m1 = _parse_success_blocks(stdout1)
    _assert_success_and_schema_valid(s1, o1, e1, m1)

    # 2) replay must succeed and return identical output (cache hit)
    env_replay = {
        "ORCHESTRA_ROLEPACK": "v1_llm",
        "LLM_MODE": "replay",
        "LLM_CACHE_DIR": str(tmp_path),
    }
    _, stdout2, _ = _run_cli("hello", env_overrides=env_replay, expect_success=True)
    s2, o2, e2, m2 = _parse_success_blocks(stdout2)
    _assert_success_and_schema_valid(s2, o2, e2, m2)

    assert (s1, o1, e1, m1) == (s2, o2, e2, m2)
