from __future__ import annotations

import os
import pytest

from extensions.cognitive.cognitive_expander_v1 import CognitiveExpanderConfig, run_cognitive_expander_v1


def test_replay_miss_fail_closed(tmp_path):
    cfg = CognitiveExpanderConfig(
        cognitive_mode="llm",
        llm_mode="replay",
        llm_provider="stub",
        cache_dir=str(tmp_path / "cache"),
    )
    with pytest.raises(RuntimeError) as e:
        run_cognitive_expander_v1(
            problem_model_v1={"baseline_problem": "x"},
            conversation_turns=[{"role": "user", "text": "x"}],
            cfg=cfg,
        )
    assert "REPLAY MISS" in str(e.value)


def test_record_writes_cache_then_replay_hits(tmp_path):
    cache_dir = tmp_path / "cache"
    cfg_record = CognitiveExpanderConfig(
        cognitive_mode="llm",
        llm_mode="record",
        llm_provider="stub",
        cache_dir=str(cache_dir),
    )
    rec1 = run_cognitive_expander_v1(
        problem_model_v1={"baseline_problem": "x"},
        conversation_turns=[{"role": "user", "text": "x"}],
        cfg=cfg_record,
    )
    key = rec1["stable_input_key"]
    assert (cache_dir / f"{key}.json").exists()

    cfg_replay = CognitiveExpanderConfig(
        cognitive_mode="llm",
        llm_mode="replay",
        llm_provider="stub",
        cache_dir=str(cache_dir),
    )
    rec2 = run_cognitive_expander_v1(
        problem_model_v1={"baseline_problem": "x"},
        conversation_turns=[{"role": "user", "text": "x"}],
        cfg=cfg_replay,
    )
    assert rec2["stable_input_key"] == rec1["stable_input_key"]
    assert rec2["policy_version"] == rec1["policy_version"]
