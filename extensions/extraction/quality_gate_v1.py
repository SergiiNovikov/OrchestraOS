from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Tuple


@dataclass(frozen=True)
class StrategicQualityGateConfig:
    min_quality_score: float = 0.70
    max_open_questions: int = 3


def _anti_generic_goal_score(goals: List[str]) -> float:
    if not goals:
        return 0.0
    # Penalize generic boilerplate phrases.
    generic = ["улучшить", "оптимизировать", "сделать лучше", "повысить эффективность"]
    g = " ".join(goals).lower()
    if any(x in g for x in generic) and len(g) < 80:
        return 0.2
    return 0.8


def _measurable_success_score(success_criteria: List[str]) -> float:
    if not success_criteria:
        return 0.0
    # "Measurable" can be non-numeric but must be checkable signal
    tokens = ["порог", "метрика", "%", "процент", "время", "latency", "roi", "cpa", "nps", "конверси", "выручк", "retention"]
    s = " ".join(success_criteria).lower()
    if any(t in s for t in tokens):
        return 0.9
    return 0.5  # still possibly measurable but weakly specified


def _next_pressure_question(open_questions: List[str], contradictions: bool) -> str:
    if contradictions:
        return "Есть противоречия в ожиданиях. Что важнее, если придётся выбрать: скорость, качество или стоимость — и почему?"
    if "measurable_success" in open_questions:
        return "Как вы проверите успех: какой сигнал/порог означает «Бинго»?"
    if "strategic_goal" in open_questions:
        return "Какой бизнес-результат вы хотите получить (не симптом), и что станет иначе после решения?"
    if open_questions:
        return f"Самый важный открытый вопрос: {open_questions[0]}. Что вы выбираете как приоритет?"
    return "Что должно стать иначе, чтобы вы сказали «Бинго/утверждаю»?"


def run_quality_gate_v1(
    *,
    requirement_model_v1: Dict[str, Any],
    cfg: StrategicQualityGateConfig = StrategicQualityGateConfig(),
) -> Dict[str, Any]:
    goals = requirement_model_v1.get("goals", []) or []
    success = requirement_model_v1.get("success_criteria", []) or []
    open_q = requirement_model_v1.get("open_questions", []) or []
    contradictions = bool(requirement_model_v1.get("contradictions_detected", False))

    goal_score = _anti_generic_goal_score(goals)
    success_score = _measurable_success_score(success)

    # Quality is a simple judge:
    # - must have at least some goal signal
    # - must have some measurable success signal
    # - open questions capped
    # - contradictions force refinement
    oq_penalty = 0.0
    if len(open_q) > cfg.max_open_questions:
        oq_penalty = 0.2

    base = (0.55 * goal_score) + (0.45 * success_score)
    quality = max(0.0, min(1.0, base - oq_penalty))

    needs_refinement = contradictions or (quality < cfg.min_quality_score) or (len(open_q) > cfg.max_open_questions)

    return {
        "strategic_quality_score": quality,
        "needs_refinement": needs_refinement,
        "next_question": _next_pressure_question(open_q, contradictions),
        "reasons": {
            "goal_score": goal_score,
            "success_score": success_score,
            "open_questions": open_q,
            "contradictions": contradictions,
        },
    }
