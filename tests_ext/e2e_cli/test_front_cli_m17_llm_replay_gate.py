from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from extensions.architect.architect_v1 import ARCHITECT_POLICY_VERSION, stable_architect_input_key
from extensions.conversation.requirement_model_v1 import default_model
from extensions.spec_writer.spec_writer_v1 import canonical_requirement_model_json, source_hash_requirement_model

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_state_ready_for_spec(work_dir: Path, conv_id: str) -> dict:
    # minimal ready_for_spec model
    m = default_model()
    m["goal"] = "LLM spec test"
    m["users"] = ["User"]
    m["success_criteria"] = ["Spec generated"]
    m["constraints"] = ["Replay only"]
    m["status"] = "ready_for_spec"
    m["last_updated_step"] = 4
    m["open_questions"] = []

    state = {
        "schema_version": "conversation_state_v1",
        "conversation_id": conv_id,
        "step": 4,
        "pending_question_id": None,
        "requirement_model_v1": m,
    }

    conv_dir = work_dir / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)
    (conv_dir / f"{conv_id}.json").write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return state


def test_m17_replay_gate_cache_miss_then_hit(tmp_path: Path) -> None:
    work_dir = tmp_path / ".orchestraos"
    work_dir.mkdir(parents=True, exist_ok=True)

    # profile with work_dir only
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / "test_profile.json"
    profile_path.write_text(json.dumps({"work_dir": str(work_dir)}, ensure_ascii=False), encoding="utf-8")

    # LLM cache dir isolated for this test
    llm_cache_dir = tmp_path / "_llm_cache"
    llm_cache_dir.mkdir(parents=True, exist_ok=True)

    conv_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    state = _write_state_ready_for_spec(work_dir, conv_id)
    model = state["requirement_model_v1"]

    key = stable_architect_input_key(policy_version=ARCHITECT_POLICY_VERSION, model=model)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # M17 switches
    env["ORCHESTRA_SPEC_MODE"] = "llm"
    env["LLM_MODE"] = "replay"
    env["LLM_CACHE_DIR"] = str(llm_cache_dir)

    # 1) replay cache miss -> fail-closed, non-zero
    cp1 = subprocess.run(
        [sys.executable, "-m", "apps.front_cli", "--conversation", conv_id, "--profile", str(profile_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert cp1.returncode != 0
    assert "Replay cache miss" in (cp1.stderr + cp1.stdout)

    # ensure state not marked done
    state_path = work_dir / "conversations" / f"{conv_id}.json"
    st1 = json.loads(state_path.read_text(encoding="utf-8"))
    assert st1["requirement_model_v1"]["status"] == "ready_for_spec"
    assert "spec_document_v1" not in st1

    # 2) write replay cache entry
    parsed = {
        "schema_version": "architect_output_v1",
        "title": "LLM Spec Title",
        "overview": "Overview text",
        "users": ["User"],
        "scope_in": [],
        "scope_out": [],
        "success_criteria": ["Spec generated"],
        "constraints": ["Replay only"],
        "assumptions": [],
        "open_questions": [],
        "acceptance_criteria": ["AC1: Spec generated"],
        "definition_of_done": ["DoD1"],
    }
    record = {
        "schema_version": "architect_llm_record_v1",
        "policy_version": ARCHITECT_POLICY_VERSION,
        "key": key,
        "mode": "record",
        "provider": "mock",
        "prompt": "dummy",
        "raw_completion": json.dumps(parsed, ensure_ascii=False),
        "parsed_json": parsed,
    }
    (llm_cache_dir / f"{key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) replay cache hit -> success, status done, spec persisted
    cp2 = subprocess.run(
        [sys.executable, "-m", "apps.front_cli", "--conversation", conv_id, "--profile", str(profile_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert cp2.returncode == 0, f"stdout:\n{cp2.stdout}\nstderr:\n{cp2.stderr}"
    assert "=== SPEC_v1 ===" in cp2.stdout
    assert "Spec v1 (LLM Draft)" in cp2.stdout

    st2 = json.loads(state_path.read_text(encoding="utf-8"))
    assert st2["requirement_model_v1"]["status"] == "done"
    spec = st2["spec_document_v1"]
    assert spec["schema_version"] == "spec_document_v1"
    gen = spec["generated_from"]
    assert gen["llm_mode"] == "replay"
    assert gen["llm_cache_key"] == key
    assert gen["architect_policy_version"] == ARCHITECT_POLICY_VERSION
