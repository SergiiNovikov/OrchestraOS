from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_problem_model_viewer_prints_current_state(tmp_path: Path) -> None:
    work_dir = tmp_path / ".orchestraos"
    work_dir.mkdir(parents=True, exist_ok=True)

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / "test_profile.json"
    profile_path.write_text(json.dumps({"work_dir": str(work_dir)}, ensure_ascii=False), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LLM_MODE"] = "off"
    env["ORCHESTRA_COGNITIVE_MODE"] = "auto"
    env["ORCHESTRA_SPEC_MODE"] = "rules"

    stdin_text = "\n".join(
        [
            "Need a deterministic offline problem discovery loop.",
            "",
        ]
    )

    cp = subprocess.run(
        [sys.executable, "-m", "apps.front_cli", "--new-conversation", "--profile", str(profile_path)],
        cwd=str(REPO_ROOT),
        env=env,
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert cp.returncode == 0, f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    assert "conversation_id:" in cp.stdout

    conv_id = None
    for line in cp.stdout.splitlines():
        if line.startswith("conversation_id:"):
            conv_id = line.split(":", 1)[1].strip()
            break
    assert conv_id is not None

    cp2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.front_cli",
            "--conversation",
            conv_id,
            "--profile",
            str(profile_path),
            "--show-problem-model",
            "--problem-model-format",
            "short",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert cp2.returncode == 0, f"stdout:\n{cp2.stdout}\nstderr:\n{cp2.stderr}"
    assert "=== problem_model_v1 ===" in cp2.stdout
    assert "status:" in cp2.stdout
    assert "active_hypothesis_id:" in cp2.stdout
