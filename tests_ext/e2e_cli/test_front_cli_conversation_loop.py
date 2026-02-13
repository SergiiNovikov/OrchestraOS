from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_front_cli_conversation_loop_ready_for_spec(tmp_path: Path) -> None:
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

    stdin_text = "\n".join(
        [
            "Сформировать ТЗ для Front Manager",
            "PM, инженер (CLI)",
            "Есть outline + ready_for_spec",
            "Без сети, детерминизм, JSON state",
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
    assert "# Draft Spec Outline" in cp.stdout

    conv_dir = work_dir / "conversations"
    assert conv_dir.exists()
    files = list(conv_dir.glob("*.json"))
    assert len(files) >= 1

    m = re.search(r"conversation_id:\s*([0-9a-fA-F]+)", cp.stdout)
    assert m is not None
    conv_id = m.group(1)
    assert (conv_dir / f"{conv_id}.json").exists()
