from __future__ import annotations

from extensions.cognitive.cognitive_rules_v1 import run_rules_step
from extensions.cognitive.problem_model_v1 import append_statement, default_problem_model


def _assert_step_shape(step: dict) -> None:
    assert isinstance(step, dict)
    assert set(step.keys()) == {
        "hypothesis",
        "next_question",
        "should_stabilize",
        "stabilize_reason",
    }
    hyp = step["hypothesis"]
    assert isinstance(hyp, dict)
    for k in (
        "inferred_problem",
        "reframed_problem",
        "confidence",
        "contradictions",
        "hidden_assumptions",
        "uncertainty_areas",
    ):
        assert k in hyp

    assert isinstance(hyp["inferred_problem"], str)
    assert isinstance(hyp["reframed_problem"], str)
    assert isinstance(hyp["confidence"], (int, float))
    assert 0.0 <= float(hyp["confidence"]) <= 1.0
    for lk in ("contradictions", "hidden_assumptions", "uncertainty_areas"):
        assert isinstance(hyp[lk], list)
        assert all(isinstance(x, str) for x in hyp[lk])

    nq = step["next_question"]
    if nq is not None:
        assert isinstance(nq, dict)
        assert isinstance(nq.get("id"), str) and nq["id"].strip()
        assert isinstance(nq.get("text"), str) and nq["text"].strip()

    assert isinstance(step["should_stabilize"], bool)
    assert step["stabilize_reason"] is None or isinstance(step["stabilize_reason"], str)


def test_rules_step_returns_valid_contract_on_various_inputs() -> None:
    cases = [
        "Сделать систему без сети, детерминизм. DoD: spec generated.",
        "Implement CLI tool for problem discovery.",
        "Нужно уточнить противоречия и гипотезы, потом извлечь требования.",
        "Fix failing pytest tests; constraints: Windows; no network.",
        "Сделать как в M18: rules/llm/auto + replay-gate.",
    ]

    for text in cases:
        pm = default_problem_model()
        pm = append_statement(pm, "user", text)
        step = run_rules_step(pm)
        _assert_step_shape(step)
