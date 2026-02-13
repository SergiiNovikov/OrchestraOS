from __future__ import annotations

import re
from typing import Any, Dict, List

_ws_re = re.compile(r"\s+", re.UNICODE)


def _norm_text(s: str) -> str:
    return _ws_re.sub(" ", s.strip())


def _last_user_texts(pm: Dict[str, Any], *, n: int = 8) -> List[str]:
    out: List[str] = []
    for st in pm.get("user_statements", []):
        if isinstance(st, dict) and st.get("role") == "user" and isinstance(st.get("text"), str):
            out.append(_norm_text(st["text"]))
    return out[-n:]


def _detect_contradictions(texts: List[str]) -> List[str]:
    joined = " | ".join(texts).lower()
    contradictions: List[str] = []
    if "on-prem" in joined and "cloud" in joined:
        contradictions.append("Deployment mentions both on-prem and cloud")
    if ("без сети" in joined or "offline" in joined) and ("api" in joined or "openai" in joined or "интернет" in joined):
        contradictions.append("Mentions offline/no-network but also references external network/API")
    return contradictions


def _early_stabilize_possible(texts: List[str]) -> bool:
    """
    Deterministic heuristic used for M18 E2E:
    If user provided a concise problem + constraints + DoD in ~2 turns,
    we allow stabilization early.

    Signals:
      - goal/problem statement: "нужно", "реализовать", "problem", "задача"
      - constraints: "без сети"/"offline"/"deterministic"/"детерминизм"
      - DoD: "dod"/"критер"/"готово"/"spec"/"тз"
    """
    j = " ".join(texts).lower()
    has_goal = any(w in j for w in ["нужно", "реализ", "problem", "задач", "сделать", "implement"])
    has_constraints = any(w in j for w in ["без сети", "offline", "deterministic", "детермини", "no network"])
    has_dod = any(w in j for w in ["dod", "критер", "готово", "definition of done", "spec", "тз", "техническое задание"])
    # Also accept "и только затем генерировать spec" as DoD-ish completion signal
    has_flow = any(w in j for w in ["и только затем", "only then", "затем генер", "then generate"])
    return bool(has_goal and has_constraints and (has_dod or has_flow))


def run_rules_step(pm: Dict[str, Any]) -> Dict[str, Any]:
    """
    tests_ext contract: return EXACT keys:
      { hypothesis, next_question, should_stabilize, stabilize_reason }
    """
    texts = _last_user_texts(pm, n=8)
    n = len(texts)

    contradictions = _detect_contradictions(texts)
    hidden: List[str] = []

    if n == 0:
        inferred = ""
        reframed = ""
        confidence = 0.0
        uncertainty = ["No initial problem statement yet"]
        next_q = {"id": "q1", "text": "Опиши задачу/проблему в 1–3 предложениях (цель, контекст, ограничения)."}
        should_stabilize = False
        stabilize_reason = None
    else:
        inferred = texts[-1]
        reframed = " ".join(texts[-3:])

        # Early stabilize for crisp 2-turn statements (M18 E2E happy path)
        if n >= 2 and _early_stabilize_possible(texts) and not contradictions:
            confidence = 0.90
            uncertainty = []
            next_q = None
            should_stabilize = True
            stabilize_reason = "early stabilize: goal+constraints+DoD detected"
        else:
            # Stage-driven deterministic questioning (works for longer conversations too)
            if n == 1:
                confidence = 0.55
                uncertainty = ["Users/stakeholders unclear", "Success criteria unclear", "Constraints unclear"]
                next_q = {"id": "q2", "text": "Кто пользователь/стейкхолдер и как он будет это использовать?"}
                should_stabilize = False
                stabilize_reason = None
            elif n == 2:
                confidence = 0.70
                uncertainty = ["Success criteria unclear", "Constraints unclear"]
                next_q = {"id": "q3", "text": "Чтобы считать задачу успешной: какие 2–3 критерия успеха/DoD?"}
                should_stabilize = False
                stabilize_reason = None
            elif n == 3:
                confidence = 0.82
                uncertainty = ["Constraints unclear"]
                next_q = {"id": "q4", "text": "Какие ключевые ограничения/инварианты (сеть/офлайн, детерминизм, запреты)?"}
                should_stabilize = False
                stabilize_reason = None
            else:
                confidence = 0.90
                uncertainty = []
                next_q = None
                should_stabilize = True
                stabilize_reason = "sufficient inputs collected"

    # Contradictions override: keep exploring
    if contradictions:
        next_q = {
            "id": f"q{max(1, n) + 1}",
            "text": "Вижу потенциальное противоречие. Уточни, что считать истинным/приоритетным?",
        }
        should_stabilize = False
        stabilize_reason = None

    return {
        "hypothesis": {
            "inferred_problem": inferred,
            "reframed_problem": reframed,
            "confidence": float(confidence),
            "contradictions": contradictions,
            "hidden_assumptions": hidden,
            "uncertainty_areas": uncertainty,
        },
        "next_question": next_q,
        "should_stabilize": bool(should_stabilize),
        "stabilize_reason": stabilize_reason,
    }
