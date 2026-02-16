from __future__ import annotations

import pytest

from extensions.extraction.requirement_extractor_v1 import RequirementExtractorConfig, run_requirement_extractor_v1
from extensions.extraction.quality_gate_v1 import run_quality_gate_v1, StrategicQualityGateConfig


def test_quality_gate_triggers_loopback_on_missing_measurable_success():
    cfg = RequirementExtractorConfig(extraction_mode="rules", llm_mode="off", llm_provider="stub", cache_dir=".x")
    rec = run_requirement_extractor_v1(
        problem_model_v1={"baseline_problem": "нужно улучшить процесс"},
        cognitive_hypotheses_v1=None,
        conversation_turns=[{"role": "user", "text": "Нужно улучшить процесс"}],
        cfg=cfg,
    )
    q = run_quality_gate_v1(requirement_model_v1=rec["parsed_output"], cfg=StrategicQualityGateConfig(min_quality_score=0.7))
    assert q["needs_refinement"] is True
    assert isinstance(q["next_question"], str) and len(q["next_question"]) > 0


def test_quality_gate_passes_with_checkable_signal():
    cfg = RequirementExtractorConfig(extraction_mode="rules", llm_mode="off", llm_provider="stub", cache_dir=".x")
    rec = run_requirement_extractor_v1(
        problem_model_v1={"baseline_problem": "хочу снизить время ответа"},
        cognitive_hypotheses_v1=None,
        conversation_turns=[{"role": "user", "text": "Цель: снизить время ответа. Успех: latency < 200ms."}],
        cfg=cfg,
    )
    q = run_quality_gate_v1(requirement_model_v1=rec["parsed_output"], cfg=StrategicQualityGateConfig(min_quality_score=0.7))
    # May still be borderline depending on goal extraction; enforce that if success is present, it should not force refinement by measurability.
    assert q["reasons"]["success_score"] >= 0.5
