from __future__ import annotations

from typing import Any, Dict, List


def default_model() -> Dict[str, Any]:
    return {
        "schema_version": "requirement_model_v1",
        "status": "collecting",
        "goal": None,
        "users": [],
        "scope_in": [],
        "scope_out": [],
        "success_criteria": [],
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "last_updated_step": 0,
    }


def validate_model_fail_closed(model: Dict[str, Any]) -> None:
    if not isinstance(model, dict):
        raise ValueError("RequirementModel v1 must be a dict")
    if model.get("schema_version") != "requirement_model_v1":
        raise ValueError("Invalid schema_version for RequirementModel v1")

    status = model.get("status")
    if status not in {"collecting", "ready_for_spec", "done"}:
        raise ValueError("Invalid status")

    goal = model.get("goal")
    if goal is not None and not isinstance(goal, str):
        raise ValueError("goal must be str|null")

    def _list_str(field: str) -> None:
        v = model.get(field)
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            raise ValueError(f"{field} must be list[str]")

    for f in (
        "users",
        "scope_in",
        "scope_out",
        "success_criteria",
        "constraints",
        "assumptions",
        "open_questions",
    ):
        _list_str(f)

    lus = model.get("last_updated_step")
    if not isinstance(lus, int) or int(lus) < 0:
        raise ValueError("last_updated_step must be int >= 0")


def _split_items(answer_text: str) -> List[str]:
    raw: List[str] = []
    for line in answer_text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        raw.extend([p for p in parts if p])

    out: List[str] = []
    seen = set()
    for item in raw:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def apply_user_answer(model: Dict[str, Any], question_id: str, answer_text: str) -> Dict[str, Any]:
    validate_model_fail_closed(model)
    if not isinstance(question_id, str) or not question_id.strip():
        raise ValueError("question_id must be non-empty str")
    if not isinstance(answer_text, str):
        raise ValueError("answer_text must be str")

    m: Dict[str, Any] = {**model}
    m["last_updated_step"] = int(model["last_updated_step"]) + 1

    answer = answer_text.strip()
    if question_id == "goal":
        m["goal"] = answer if answer else None
    elif question_id in {"users", "success_criteria", "constraints", "scope_in", "scope_out", "assumptions"}:
        m[question_id] = _split_items(answer)
    else:
        raise ValueError(f"Unknown question_id: {question_id}")

    validate_model_fail_closed(m)
    return m
