from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_front_cli_m18_cognitive_loop_stabilizes_and_generates_spec(tmp_path: Path) -> None:
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
    env["LLM_MODE"] = "off"  # auto => rules
    env["ORCHESTRA_COGNITIVE_MODE"] = "auto"

    # 2 turns: first provides constraints+DoD, second provides crisp reframe.
    stdin_text = "\n".join(
        [
            "Нужно реализовать Cognitive Front Manager в conversation mode; без сети; DoD: deterministic spec.",
            "Проблема: стабилизировать model проблемы (гипотезы/неопределенности) и только затем генерировать spec.",
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
    assert "status: ready_for_spec" in cp.stdout
    assert "=== SPEC_v1 ===" in cp.stdout

    m = re.search(r"conversation_id:\s*([0-9a-fA-F]+)", cp.stdout)
    assert m is not None
    conv_id = m.group(1)

    state_path = work_dir / "conversations" / f"{conv_id}.json"
    st = json.loads(state_path.read_text(encoding="utf-8"))

    assert st["problem_model_v1"]["schema_version"] == "problem_model_v1"
    assert st["problem_model_v1"]["status"] == "stabilized"
    assert st["requirement_model_v1"]["status"] == "done"
    assert st["spec_document_v1"]["schema_version"] == "spec_document_v1"
