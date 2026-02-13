from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_front_cli_m16_prints_spec_and_persists(tmp_path: Path) -> None:
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
            "Сделать виртуального бухгалтера на основе SCA",
            "Предприятия, бухгалтер",
            "Пачка счетов -> проводки",
            "Без сети, минимальный бюджет",
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
    assert "## 8) Definition of Done" in cp.stdout

    m = re.search(r"conversation_id:\s*([0-9a-fA-F]+)", cp.stdout)
    assert m is not None
    conv_id = m.group(1)

    conv_dir = work_dir / "conversations"
    state_path = conv_dir / f"{conv_id}.json"
    assert state_path.exists()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["requirement_model_v1"]["status"] == "done"
    assert "spec_document_v1" in state

    spec = state["spec_document_v1"]
    assert spec["schema_version"] == "spec_document_v1"
    assert spec["format"] == "markdown"
    assert isinstance(spec["title"], str) and spec["title"].strip()
    assert isinstance(spec["content"], str) and "Definition of Done" in spec["content"]

    gen = spec["generated_from"]
    assert gen["conversation_id"] == conv_id
    assert gen["requirement_model_version"] == "requirement_model_v1"
    assert isinstance(gen["source_hash"], str) and len(gen["source_hash"]) == 64
