from __future__ import annotations

import json
from pathlib import Path

import pytest

from extensions.cognitive.cognitive_llm_v1 import (
    COGNITIVE_POLICY_VERSION,
    stable_cognitive_input_key,
    run_llm_step,
)
from extensions.cognitive.problem_model_v1 import append_statement, default_problem_model
from extensions.cognitive.settings import read_cognitive_settings_from_env


def test_llm_replay_gate_cache_miss_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llm_cache_dir = tmp_path / "_llm_cache"
    llm_cache_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ORCHESTRA_COGNITIVE_MODE", "llm")
    monkeypatch.setenv("LLM_MODE", "replay")
    monkeypatch.setenv("LLM_CACHE_DIR", str(llm_cache_dir))

    settings = read_cognitive_settings_from_env()
    pm = default_problem_model()
    pm = append_statement(pm, "user", "Need deterministic offline cognitive loop")

    with pytest.raises(Exception):
        run_llm_step(pm=pm, settings=settings)


def test_llm_replay_gate_cache_hit_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llm_cache_dir = tmp_path / "_llm_cache"
    llm_cache_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ORCHESTRA_COGNITIVE_MODE", "llm")
    monkeypatch.setenv("LLM_MODE", "replay")
    monkeypatch.setenv("LLM_CACHE_DIR", str(llm_cache_dir))

    settings = read_cognitive_settings_from_env()
    pm = default_problem_model()
    pm = append_statement(pm, "user", "Need deterministic offline cognitive loop")

    key = stable_cognitive_input_key(pm=pm)

    parsed = {
        "hypothesis": {
            "inferred_problem": "test",
            "reframed_problem": "test reframed",
            "confidence": 0.9,
            "contradictions": [],
            "hidden_assumptions": [],
            "uncertainty_areas": [],
        },
        "next_question": None,
        "should_stabilize": True,
        "stabilize_reason": "ok",
    }
    record = {
        "schema_version": "cognitive_llm_record_v1",
        "policy_version": COGNITIVE_POLICY_VERSION,
        "key": key,
        "mode": "record",
        "provider": "mock",
        "prompt": "dummy",
        "raw_completion": json.dumps(parsed, ensure_ascii=False),
        "parsed_json": parsed,
    }
    (llm_cache_dir / f"{key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    out = run_llm_step(pm=pm, settings=settings)
    assert out["hypothesis"]["reframed_problem"] == "test reframed"
    assert out["should_stabilize"] is True
