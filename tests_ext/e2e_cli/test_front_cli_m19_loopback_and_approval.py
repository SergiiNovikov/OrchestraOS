from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(cmd, env):
    # Force deterministic UTF-8 decode regardless of Windows locale.
    p = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    return p.returncode, p.stdout, p.stderr


def test_m19_loopback_then_approval(tmp_path):
    repo_root = Path.cwd()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    # Ensure child process writes UTF-8 to pipes deterministically
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Gate M19 path (no new CLI flags)
    env["ORCHESTRA_SPEC_MODE"] = "conversation"

    env["ORCHESTRA_COGNITIVE_MODE"] = "rules"
    env["ORCHESTRA_EXTRACTION_MODE"] = "rules"
    env["ORCHESTRA_APPROVAL_REQUIRED"] = "1"
    env["ORCHESTRA_LLM_MODE"] = "off"
    env["LLM_CACHE_DIR"] = str(tmp_path / "cache")

    rc, out, err = _run([sys.executable, "-m", "apps.front_cli", "--new-conversation"], env)
    assert rc == 0, f"stderr={err}\nstdout={out}"

    rc, out, err = _run([sys.executable, "-m", "apps.front_cli", "--text", "Нужно улучшить процесс"], env)
    assert rc == 0, f"stderr={err}\nstdout={out}"
    assert "?" in out

    rc, out, err = _run([sys.executable, "-m", "apps.front_cli", "--text", "Цель: снизить время ответа. Успех: latency < 200ms."], env)
    assert rc == 0, f"stderr={err}\nstdout={out}"
    assert "Draft Spec" in out
    assert "Approval required" in out

    rc, out, err = _run([sys.executable, "-m", "apps.front_cli", "--text", "ок"], env)
    assert rc == 0, f"stderr={err}\nstdout={out}"
    assert "Approval required" in out

    rc, out, err = _run([sys.executable, "-m", "apps.front_cli", "--text", "утверждаю"], env)
    assert rc == 0, f"stderr={err}\nstdout={out}"
    assert "APPROVED" in out
