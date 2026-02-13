from __future__ import annotations

import copy

import pytest

from extensions.cognitive.problem_model_v1 import (
    apply_cognitive_step,
    append_statement,
    default_problem_model,
    validate_problem_model_fail_closed,
)


def test_problem_model_append_apply_deterministic_n3() -> None:
    pm = default_problem_model()
    pm = append_statement(pm, "user", "Нужно сделать CLI без сети; DoD: deterministic")

    step = {
        "hypothesis": {
            "inferred_problem": "Сделать CLI",
            "reframed_problem": "Стабилизировать проблему и сгенерировать spec",
            "confidence": 0.9,
            "contradictions": [],
            "hidden_assumptions": [],
            "uncertainty_areas": [],
        },
        "next_question": None,
        "should_stabilize": True,
        "stabilize_reason": "ok",
    }

    pm1 = apply_cognitive_step(copy.deepcopy(pm), step)
    pm2 = apply_cognitive_step(copy.deepcopy(pm), step)
    pm3 = apply_cognitive_step(copy.deepcopy(pm), step)

    assert pm1 == pm2 == pm3
    assert pm1["status"] == "stabilized"


def test_validate_problem_model_fail_closed_on_bad_types() -> None:
    pm = default_problem_model()
    pm["hypotheses"] = "not a list"  # type: ignore[assignment]
    with pytest.raises(Exception):
        validate_problem_model_fail_closed(pm)  # type: ignore[arg-type]
