from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from extensions.conversation.clarify_policy_v1 import draft_spec_outline, is_ready, next_question
from extensions.conversation.requirement_model_v1 import apply_user_answer, validate_model_fail_closed

ElicitResult = Tuple[Dict[str, Any], Optional[Tuple[str, str]], Optional[str]]


def _update_open_questions(model: Dict[str, Any]) -> Dict[str, Any]:
    missing: list[str] = []
    goal = model.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        missing.append("Сформулировать цель / ожидаемый результат")
    if not model.get("users"):
        missing.append("Определить пользователей и контекст")
    if not model.get("success_criteria"):
        missing.append("Определить критерии готовности")
    if not model.get("constraints"):
        missing.append("Уточнить ограничения (сроки/бюджет/платформа)")

    m2 = {**model}
    m2["open_questions"] = missing[:3]
    return m2


def elicitation_step(
    *,
    model: Dict[str, Any],
    pending_question_id: Optional[str],
    last_user_answer: Optional[str],
) -> ElicitResult:
    validate_model_fail_closed(model)

    m = model
    if pending_question_id is not None:
        if last_user_answer is None:
            raise ValueError("last_user_answer required when pending_question_id is set")
        m = apply_user_answer(m, pending_question_id, last_user_answer)

    m = _update_open_questions(m)

    if is_ready(m):
        m2 = {**m, "status": "ready_for_spec"}
        validate_model_fail_closed(m2)
        return m2, None, draft_spec_outline(m2)

    q = next_question(m)
    return m, q, None
