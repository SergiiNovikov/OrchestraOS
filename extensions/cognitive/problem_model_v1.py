from __future__ import annotations

import copy
from typing import Any, Dict, List


def default_problem_model() -> Dict[str, Any]:
    return {
        "schema_version": "problem_model_v1",
        "status": "exploring",
        "user_statements": [],
        "hypotheses": [
            {
                "id": "h1",
                "inferred_problem": "",
                "reframed_problem": "",
                "confidence": 0.0,
                "contradictions": [],
                "hidden_assumptions": [],
                "uncertainty_areas": [],
            }
        ],
        "active_hypothesis_id": "h1",
        "last_question": None,
        "turn_index": 0,
    }


def _is_list_str(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


def validate_problem_model_fail_closed(pm: Dict[str, Any]) -> None:
    if not isinstance(pm, dict):
        raise ValueError("ProblemModel v1 must be a dict")
    if pm.get("schema_version") != "problem_model_v1":
        raise ValueError("Invalid schema_version for ProblemModel v1")

    status = pm.get("status")
    if status not in {"exploring", "stabilized"}:
        raise ValueError("Invalid problem_model_v1.status")

    us = pm.get("user_statements")
    if not isinstance(us, list):
        raise ValueError("user_statements must be a list")
    for i, st in enumerate(us):
        if not isinstance(st, dict):
            raise ValueError(f"user_statements[{i}] must be an object")
        if st.get("role") not in {"user", "assistant"}:
            raise ValueError(f"user_statements[{i}].role must be 'user'|'assistant'")
        if not isinstance(st.get("text"), str):
            raise ValueError(f"user_statements[{i}].text must be str")

    hs = pm.get("hypotheses")
    if not isinstance(hs, list) or not hs:
        raise ValueError("hypotheses must be a non-empty list")
    ids: List[str] = []
    for i, h in enumerate(hs):
        if not isinstance(h, dict):
            raise ValueError(f"hypotheses[{i}] must be an object")
        hid = h.get("id")
        if not isinstance(hid, str) or not hid.strip():
            raise ValueError(f"hypotheses[{i}].id must be non-empty str")
        ids.append(hid)

        for f in ("inferred_problem", "reframed_problem"):
            if not isinstance(h.get(f), str):
                raise ValueError(f"hypotheses[{i}].{f} must be str")

        conf = h.get("confidence")
        if not isinstance(conf, (int, float)):
            raise ValueError(f"hypotheses[{i}].confidence must be number")
        if float(conf) < 0.0 or float(conf) > 1.0:
            raise ValueError(f"hypotheses[{i}].confidence must be in [0,1]")

        for lf in ("contradictions", "hidden_assumptions", "uncertainty_areas"):
            if not _is_list_str(h.get(lf)):
                raise ValueError(f"hypotheses[{i}].{lf} must be list[str]")

    ah = pm.get("active_hypothesis_id")
    if not isinstance(ah, str) or ah not in set(ids):
        raise ValueError("active_hypothesis_id must reference an existing hypothesis id")

    lq = pm.get("last_question")
    if lq is not None:
        if not isinstance(lq, dict):
            raise ValueError("last_question must be object|null")
        if not isinstance(lq.get("id"), str) or not lq["id"].strip():
            raise ValueError("last_question.id must be non-empty str")
        if not isinstance(lq.get("text"), str) or not lq["text"].strip():
            raise ValueError("last_question.text must be non-empty str")

    ti = pm.get("turn_index")
    if not isinstance(ti, int) or int(ti) < 0:
        raise ValueError("turn_index must be int >= 0")


def append_statement(pm: Dict[str, Any], role: str, text: str) -> Dict[str, Any]:
    validate_problem_model_fail_closed(pm)
    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user'|'assistant'")
    if not isinstance(text, str):
        raise ValueError("text must be str")
    t = text.strip()
    if not t:
        return pm

    pm2 = copy.deepcopy(pm)
    pm2["user_statements"].append({"role": role, "text": t})
    validate_problem_model_fail_closed(pm2)
    return pm2


def _get_active_hypothesis(pm: Dict[str, Any]) -> Dict[str, Any]:
    ah = pm["active_hypothesis_id"]
    for h in pm["hypotheses"]:
        if h["id"] == ah:
            return h
    raise ValueError("active_hypothesis_id not found")


def apply_cognitive_step(pm: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
    validate_problem_model_fail_closed(pm)
    if not isinstance(step, dict):
        raise ValueError("cognitive_step_v1 must be dict")

    hyp = step.get("hypothesis")
    if not isinstance(hyp, dict):
        raise ValueError("cognitive_step_v1.hypothesis must be dict")

    next_q = step.get("next_question")
    if next_q is not None:
        if not isinstance(next_q, dict):
            raise ValueError("next_question must be dict|null")
        if not isinstance(next_q.get("id"), str) or not next_q["id"].strip():
            raise ValueError("next_question.id must be non-empty str")
        if not isinstance(next_q.get("text"), str) or not next_q["text"].strip():
            raise ValueError("next_question.text must be non-empty str")

    should_stabilize = step.get("should_stabilize")
    if not isinstance(should_stabilize, bool):
        raise ValueError("should_stabilize must be bool")
    sr = step.get("stabilize_reason")
    if sr is not None and not isinstance(sr, str):
        raise ValueError("stabilize_reason must be str|null")

    pm2 = copy.deepcopy(pm)

    h = _get_active_hypothesis(pm2)
    for k in (
        "inferred_problem",
        "reframed_problem",
        "confidence",
        "contradictions",
        "hidden_assumptions",
        "uncertainty_areas",
    ):
        if k not in hyp:
            raise ValueError(f"hypothesis.{k} missing")

    h["inferred_problem"] = str(hyp["inferred_problem"])
    h["reframed_problem"] = str(hyp["reframed_problem"])
    h["confidence"] = float(hyp["confidence"])
    h["contradictions"] = list(hyp["contradictions"])
    h["hidden_assumptions"] = list(hyp["hidden_assumptions"])
    h["uncertainty_areas"] = list(hyp["uncertainty_areas"])

    pm2["last_question"] = next_q

    if should_stabilize:
        pm2["status"] = "stabilized"

    validate_problem_model_fail_closed(pm2)
    return pm2
