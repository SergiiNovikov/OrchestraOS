from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, Tuple


MARKERS = (
    "=== output_summary ===",
    "=== output ===",
    "=== runtime_error ===",
    "=== run_manifest ===",
)


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


def _run_cli(text: str, *, env_overrides: Dict[str, str] | None = None) -> Tuple[dict, dict, Any, dict]:
    cmd = [sys.executable, "-m", "apps.front_cli", "--text", text]
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


def test_rolepack_env_selects_v1_tz_and_produces_final_response() -> None:
    summary, output, runtime_error, manifest = _run_cli(
        "hello",
        env_overrides={"ORCHESTRA_ROLEPACK": "v1_tz"},
    )

    assert runtime_error is None
    assert manifest["final_outcome"]["status"] == "success"

    # With v1_tz fully wired, final output is final_response_artifact_v0 (not nested {"stage": ...})
    assert output.get("schema_version") == "final_response_artifact_v0"
    assert output["execution_status"]["status"] in ("success", "failure")
    assert isinstance(output["results"], list) and len(output["results"]) > 0


def test_rolepack_v1_tz_determinism_n3() -> None:
    s1, o1, e1, m1 = _run_cli("hello", env_overrides={"ORCHESTRA_ROLEPACK": "v1_tz"})
    s2, o2, e2, m2 = _run_cli("hello", env_overrides={"ORCHESTRA_ROLEPACK": "v1_tz"})
    s3, o3, e3, m3 = _run_cli("hello", env_overrides={"ORCHESTRA_ROLEPACK": "v1_tz"})

    assert (s1, o1, e1, m1) == (s2, o2, e2, m2) == (s3, o3, e3, m3)


def test_rolepack_unknown_fail_closed() -> None:
    cmd = [sys.executable, "-m", "apps.front_cli", "--text", "hello"]
    env = os.environ.copy()
    env["ORCHESTRA_ROLEPACK"] = "does_not_exist"

    res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    assert res.returncode != 0
