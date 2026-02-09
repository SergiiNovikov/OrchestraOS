from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_front_cli_single_shot_smoke(tmp_path: Path) -> None:
    # isolate workdir for this test
    work_dir = tmp_path / ".orchestraos"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Create a temporary profile that sets work_dir (profile file may be empty in repo)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / "test_profile.json"
    profile_path.write_text(json.dumps({"work_dir": str(work_dir)}, ensure_ascii=False), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)

    cp = subprocess.run(
        [sys.executable, "-m", "apps.front_cli", "--text", "hello", "--profile", str(profile_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    assert cp.returncode == 0, f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    assert "=== output_summary ===" in cp.stdout
    assert "=== run_manifest ===" in cp.stdout

    # Extract trace_id from stdout summary JSON
    # We keep it simple: find the first occurrence of '"trace_id":'
    assert '"trace_id"' in cp.stdout

    # Verify at least one run directory exists
    runs_dir = work_dir / "runs"
    assert runs_dir.exists()
    subdirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    assert len(subdirs) >= 1

    # Verify run_manifest.json exists in the newest directory (by mtime)
    newest = max(subdirs, key=lambda p: p.stat().st_mtime)
    assert (newest / "run_manifest.json").exists()
