from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from extensions.conversation.requirement_model_v1 import validate_model_fail_closed

Question = Tuple[str, str]


def _is_empty_str(x: Any) -> bool:
    return not isinstance(x, str) or not x.strip()


def is_ready(model: Dict[str, Any]) -> bool:
    validate_model_fail_closed(model)
    if _is_empty_str(model.get("goal")):
        return False
    if not model.get("users"):
        return False
    if not model.get("success_criteria"):
        return False
    if not model.get("constraints"):
        return False
    return True


def next_question(model: Dict[str, Any]) -> Optional[Question]:
    validate_model_fail_closed(model)

    if _is_empty_str(model.get("goal")):
        return ("goal", "Какой результат вы хотите получить?")
    if not model.get("users"):
        return ("users", "Кто будет пользоваться и в каком контексте?")
    if not model.get("success_criteria"):
        return ("success_criteria", "Как поймём, что готово?")
    if not model.get("constraints"):
        return ("constraints", "Есть ли ограничения по срокам/бюджету/платформе?")
    return None


def draft_spec_outline(model: Dict[str, Any]) -> str:
    validate_model_fail_closed(model)

    goal = model.get("goal") if isinstance(model.get("goal"), str) else None

    md = "# Draft Spec Outline\n\n"
    md += "## 1) Goal\n\n"
    md += (goal.strip() if goal else "_TBD_") + "\n\n"

    md += "## 2) Users & Context\n\n"
    md += "\n".join([f"- {u}" for u in model["users"]]) + "\n\n" if model.get("users") else "_TBD_\n\n"

    md += "## 3) Scope\n\n"
    md += "- **In-scope**: _TBD_\n" if not model.get("scope_in") else "- **In-scope**:\n" + "\n".join([f"  - {x}" for x in model["scope_in"]]) + "\n"
    md += "- **Out-of-scope**: _TBD_\n\n" if not model.get("scope_out") else "- **Out-of-scope**:\n" + "\n".join([f"  - {x}" for x in model["scope_out"]]) + "\n\n"

    md += "## 4) Success Criteria\n\n"
    md += "\n".join([f"- {s}" for s in model["success_criteria"]]) + "\n\n" if model.get("success_criteria") else "_TBD_\n\n"

    md += "## 5) Constraints\n\n"
    md += "\n".join([f"- {c}" for c in model["constraints"]]) + "\n\n" if model.get("constraints") else "_TBD_\n\n"

    md += "## 6) Assumptions\n\n"
    md += "\n".join([f"- {a}" for a in model["assumptions"]]) + "\n\n" if model.get("assumptions") else "_TBD_\n\n"

    md += "## 7) Open Questions\n\n"
    oq = model.get("open_questions")
    md += "\n".join([f"- {q}" for q in oq]) + "\n" if isinstance(oq, list) and oq else "_None_\n"
    return md
