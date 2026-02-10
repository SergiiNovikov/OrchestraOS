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
    """
    Extract JSON object printed after a marker line.
    The CLI prints blocks like:

      === output_summary ===
      { ...json... }

    We parse from the first '{' or 'n' (null) after marker until before next marker or end.
    """
    idx = stdout.find(marker)
    if idx < 0:
        raise AssertionError(f"Marker not found in stdout: {marker}")

    # start search after marker line
    start = idx + len(marker)
    # skip whitespace/newlines
    while start < len(stdout) and stdout[start] in " \r\n\t":
        start += 1

    # find end: next marker or EOF
    next_positions = []
    for m in MARKERS:
        if m == marker:
            continue
        p = stdout.find(m, start)
        if p >= 0:
            next_positions.append(p)
    end = min(next_positions) if next_positions else len(stdout)

    blob = stdout[start:end].strip()

    # Some blocks may be "null"
    return json.loads(blob)


def _run_cli(text: str) -> Tuple[Dict[str, Any], Dict[str, Any], Any, Dict[str, Any]]:
    cmd = [sys.executable, "-m", "apps.front_cli", "--text", text]

    env = os.environ.copy()
    # Keep deterministic environment; no need to set rolepack unless you later add switching.
    # env["ORCHESTRA_ROLEPACK"] = "v1_tz"

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    if res.returncode != 0:
        raise AssertionError(
            f"CLI returned non-zero exit code: {res.returncode}\n"
            f"STDOUT:\n{res.stdout}\n"
            f"STDERR:\n{res.stderr}\n"
        )

    stdout = res.stdout

    output_summary = _extract_json_block(stdout, "=== output_summary ===")
    output = _extract_json_block(stdout, "=== output ===")
    runtime_error = _extract_json_block(stdout, "=== runtime_error ===")
    run_manifest_wrapper = _extract_json_block(stdout, "=== run_manifest ===")

    if not isinstance(output_summary, dict):
        raise AssertionError("output_summary must be a JSON object")
    if not isinstance(output, dict):
        raise AssertionError("output must be a JSON object")
    if not isinstance(run_manifest_wrapper, dict):
        raise AssertionError("run_manifest must be a JSON object")

    # The file prints {"run_manifest": {...}}
    run_manifest = run_manifest_wrapper.get("run_manifest")
    if not isinstance(run_manifest, dict):
        raise AssertionError("run_manifest.run_manifest must be a JSON object")

    return output_summary, output, runtime_error, run_manifest


def test_front_cli_e2e_live_roles_v1_tz_golden() -> None:
    summary, output, runtime_error, manifest = _run_cli("hello")

    assert runtime_error is None

    assert summary["baseline_norm"] == "hello"
    assert summary["stages"] == [
        "scope_resolver",
        "intent_interpreter",
        "task_decomposer",
        "role_orchestrator",
        "execution_roles",
        "result_assembler",
    ]
    assert isinstance(summary.get("trace_id"), str) and summary["trace_id"]

    # Manifest success
    final_outcome = manifest["final_outcome"]
    assert final_outcome["status"] == "success"
    assert isinstance(final_outcome.get("final_artifact_hash"), str) and final_outcome["final_artifact_hash"]

    # Ensure trace id matches in manifest identity
    assert manifest["run_identity"]["trace_id"] == summary["trace_id"]

    # Output shape sanity: should end at result_assembler
    assert output.get("stage") == "result_assembler"


def test_front_cli_e2e_live_roles_v1_tz_determinism_n3() -> None:
    s1, o1, e1, m1 = _run_cli("hello")
    s2, o2, e2, m2 = _run_cli("hello")
    s3, o3, e3, m3 = _run_cli("hello")

    assert (s1, o1, e1, m1) == (s2, o2, e2, m2) == (s3, o3, e3, m3)
