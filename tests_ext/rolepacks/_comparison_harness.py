from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


MARKERS = (
    "=== output_summary ===",
    "=== output ===",
    "=== runtime_error ===",
    "=== run_manifest ===",
)


@dataclass(frozen=True)
class CliRun:
    summary: dict
    output: dict
    runtime_error: Any
    manifest: dict
    raw_stdout: str
    raw_stderr: str


def _extract_json_block(stdout: str, marker: str) -> Any:
    if not isinstance(stdout, str):
        raise AssertionError(f"CLI stdout must be str, got: {type(stdout)}")

    idx = stdout.find(marker)
    if idx < 0:
        raise AssertionError(f"Marker not found in CLI stdout: {marker}\nSTDOUT:\n{stdout}")

    start = idx + len(marker)
    while start < len(stdout) and stdout[start] in " \r\n\t":
        start += 1

    next_positions: List[int] = []
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


def run_front_cli(text: str, *, rolepack: str) -> CliRun:
    cmd = [sys.executable, "-m", "apps.front_cli", "--text", text]

    env = os.environ.copy()
    env["ORCHESTRA_ROLEPACK"] = rolepack

    # Windows-friendly:
    # 1) Force child process to prefer UTF-8 for its own I/O.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    # 2) Force parent-side decoding to UTF-8 with replacement so we never crash
    #    on undecodable bytes (cp1252/cp1251 environments can choke otherwise).
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )

    if res.returncode != 0:
        raise AssertionError(
            "CLI failed\n"
            f"rolepack={rolepack!r}\n"
            f"exit={res.returncode}\n"
            f"STDOUT:\n{res.stdout}\n"
            f"STDERR:\n{res.stderr}\n"
        )

    stdout = res.stdout if isinstance(res.stdout, str) else ""
    stderr = res.stderr if isinstance(res.stderr, str) else ""

    summary = _extract_json_block(stdout, "=== output_summary ===")
    output = _extract_json_block(stdout, "=== output ===")
    runtime_error = _extract_json_block(stdout, "=== runtime_error ===")
    run_manifest_wrapper = _extract_json_block(stdout, "=== run_manifest ===")

    if not isinstance(run_manifest_wrapper, dict) or "run_manifest" not in run_manifest_wrapper:
        raise AssertionError(
            "CLI did not emit run_manifest wrapper as expected.\n"
            f"rolepack={rolepack!r}\n"
            f"wrapper={run_manifest_wrapper!r}\n"
            f"STDOUT:\n{stdout}\n"
        )

    manifest = run_manifest_wrapper["run_manifest"]

    if not isinstance(summary, dict) or not isinstance(output, dict) or not isinstance(manifest, dict):
        raise AssertionError(
            "CLI JSON blocks have unexpected types.\n"
            f"rolepack={rolepack!r}\n"
            f"summary={type(summary)} output={type(output)} manifest={type(manifest)}\n"
        )

    return CliRun(
        summary=summary,
        output=output,
        runtime_error=runtime_error,
        manifest=manifest,
        raw_stdout=stdout,
        raw_stderr=stderr,
    )


def _assert_success_common(run: CliRun) -> None:
    if run.runtime_error is not None:
        raise AssertionError(f"runtime_error is not None: {run.runtime_error!r}")

    final = run.manifest.get("final_outcome")
    if not isinstance(final, dict) or final.get("status") != "success":
        raise AssertionError(f"manifest.final_outcome.status != 'success': {final!r}")


def assert_schema_valid_and_success(run: CliRun, *, rolepack: str) -> None:
    _assert_success_common(run)

    # The 'deterministic' rolepack is a harness/debug pipeline that does NOT emit v0 schema artifacts.
    if rolepack == "deterministic":
        if not isinstance(run.output, dict):
            raise AssertionError("deterministic output must be a dict")
        return

    schema_version = run.output.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        raise AssertionError(f"output.schema_version must be a non-empty string, got: {schema_version!r}")

    from validation.schemas import validate_artifact_v0

    validate_artifact_v0(artifact=run.output, expected_schema_version=schema_version)


def assert_determinism_n3(text: str, *, rolepack: str) -> Tuple[CliRun, CliRun, CliRun]:
    r1 = run_front_cli(text, rolepack=rolepack)
    r2 = run_front_cli(text, rolepack=rolepack)
    r3 = run_front_cli(text, rolepack=rolepack)

    assert_schema_valid_and_success(r1, rolepack=rolepack)
    assert_schema_valid_and_success(r2, rolepack=rolepack)
    assert_schema_valid_and_success(r3, rolepack=rolepack)

    t1 = (r1.summary, r1.output, r1.runtime_error, r1.manifest)
    t2 = (r2.summary, r2.output, r2.runtime_error, r2.manifest)
    t3 = (r3.summary, r3.output, r3.runtime_error, r3.manifest)

    if not (t1 == t2 == t3):
        raise AssertionError(
            "Determinism N=3 failed: outputs differ across runs.\n"
            f"rolepack={rolepack!r}\n"
            f"Run1 summary={r1.summary!r}\n"
            f"Run2 summary={r2.summary!r}\n"
            f"Run3 summary={r3.summary!r}\n"
        )

    return r1, r2, r3


def build_snapshot_record(rolepack: str, run: CliRun) -> dict:
    schema = run.output.get("schema_version") if isinstance(run.output, dict) else None

    return {
        "rolepack": rolepack,
        "output_schema": schema,
        "manifest_status": (run.manifest.get("final_outcome") or {}).get("status"),
        "output_summary_keys": sorted(list(run.summary.keys())),
        "output_keys": sorted(list(run.output.keys())) if isinstance(run.output, dict) else None,
        "results_count": len(run.output.get("results", [])) if isinstance(run.output.get("results"), list) else None,
        "trace_id": run.summary.get("trace_id"),
        "stages": run.summary.get("stages"),
        "baseline_norm": run.summary.get("baseline_norm"),
        "full": {
            "summary": run.summary,
            "output": run.output,
            "manifest": run.manifest,
        },
    }


def write_snapshot_file(records: List[dict], *, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "snapshot_kind": "rolepack_comparison",
        "records": records,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
