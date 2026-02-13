from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from extensions.conversation.requirement_model_v1 import validate_model_fail_closed


def _nonempty_str(x: Any) -> str | None:
    if isinstance(x, str) and x.strip():
        return x.strip()
    return None


def _md_list(items: List[str], *, empty: str = "_TBD_") -> str:
    if not items:
        return empty
    return "\n".join([f"- {x}" for x in items])


def canonical_requirement_model_json(model: Dict[str, Any]) -> str:
    """Deterministic canonical JSON used for hashing."""
    validate_model_fail_closed(model)
    return json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_hash_requirement_model(model: Dict[str, Any]) -> str:
    canon = canonical_requirement_model_json(model)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _definition_of_done(model: Dict[str, Any]) -> List[str]:
    dod: List[str] = []

    goal = _nonempty_str(model.get("goal"))
    if goal:
        dod.append(f"Сформулирована цель: {goal}")

    users = model.get("users", [])
    if users:
        dod.append(f"Определены пользователи/контекст ({len(users)} пункт(а/ов))")

    sc = model.get("success_criteria", [])
    if sc:
        dod.append(f"Зафиксированы критерии готовности ({len(sc)} пункт(а/ов))")

    constraints = model.get("constraints", [])
    if constraints:
        dod.append(f"Зафиксированы ограничения ({len(constraints)} пункт(а/ов))")

    # Deterministic quality gates
    dod.extend(
        [
            "Есть список In-scope и Out-of-scope (если TBD — явно отмечено в ТЗ)",
            "Есть раздел 'Open Questions' (если пусто — явно None)",
            "Есть критерии приёмки (Acceptance Criteria) в проверяемом виде",
        ]
    )
    return dod


def render_spec_markdown(model: Dict[str, Any]) -> str:
    """Render a structured spec in Markdown deterministically."""
    validate_model_fail_closed(model)

    goal = _nonempty_str(model.get("goal")) or "_TBD_"
    users = model.get("users", [])
    scope_in = model.get("scope_in", [])
    scope_out = model.get("scope_out", [])
    success = model.get("success_criteria", [])
    constraints = model.get("constraints", [])
    assumptions = model.get("assumptions", [])
    open_q = model.get("open_questions", [])

    md = ""
    md += "# Spec v1 (Draft)\n\n"
    md += "## 1) Overview\n\n"
    md += f"**Goal:** {goal}\n\n"

    md += "## 2) Users & Context\n\n"
    md += _md_list(users) + "\n\n"

    md += "## 3) Scope\n\n"
    md += "### In-scope\n\n"
    md += _md_list(scope_in) + "\n\n"
    md += "### Out-of-scope\n\n"
    md += _md_list(scope_out) + "\n\n"

    md += "## 4) Success Criteria\n\n"
    md += _md_list(success) + "\n\n"

    md += "## 5) Constraints\n\n"
    md += _md_list(constraints) + "\n\n"

    md += "## 6) Assumptions\n\n"
    md += _md_list(assumptions) + "\n\n"

    md += "## 7) Acceptance Criteria\n\n"
    if success:
        md += _md_list([f"AC{i+1}: {s}" for i, s in enumerate(success)], empty="_TBD_") + "\n\n"
    else:
        md += "_TBD_\n\n"

    md += "## 8) Definition of Done\n\n"
    md += _md_list(_definition_of_done(model), empty="_TBD_") + "\n\n"

    md += "## 9) Open Questions\n\n"
    md += _md_list(open_q, empty="_None_") + "\n"

    return md


def build_spec_document_v1(*, model: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    """Build structured spec_document_v1 with deterministic source_hash."""
    validate_model_fail_closed(model)
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id must be non-empty str")

    title = _nonempty_str(model.get("goal")) or "Spec v1 (Draft)"
    content = render_spec_markdown(model)
    src_hash = source_hash_requirement_model(model)

    return {
        "schema_version": "spec_document_v1",
        "format": "markdown",
        "title": title,
        "content": content,
        "generated_from": {
            "conversation_id": conversation_id,
            "requirement_model_version": "requirement_model_v1",
            "source_hash": src_hash,
        },
    }
