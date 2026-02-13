from __future__ import annotations

import json
from typing import Any, Dict, Optional


def _truncate(s: str, n: int = 280) -> str:
    s2 = " ".join(s.strip().split())
    if len(s2) <= n:
        return s2
    return s2[: max(0, n - 1)] + "…"


def _active_hypothesis(pm: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ah = pm.get("active_hypothesis_id")
    for h in pm.get("hypotheses", []):
        if isinstance(h, dict) and h.get("id") == ah:
            return h
    return None


def format_problem_model_view(pm: Dict[str, Any], *, style: str = "short") -> str:
    if style not in {"short", "json"}:
        raise ValueError("style must be 'short'|'json'")

    if style == "json":
        return json.dumps(pm, ensure_ascii=False, indent=2, sort_keys=True)

    status = pm.get("status")
    turn_index = pm.get("turn_index")
    stmts = pm.get("user_statements", [])
    stmt_count = len(stmts) if isinstance(stmts, list) else 0

    h = _active_hypothesis(pm) or {}
    inferred = _truncate(str(h.get("inferred_problem") or ""), 220)
    reframed = _truncate(str(h.get("reframed_problem") or ""), 220)
    confidence = h.get("confidence", 0.0)

    contradictions = h.get("contradictions", [])
    uncertainty = h.get("uncertainty_areas", [])
    hidden = h.get("hidden_assumptions", [])

    lq = pm.get("last_question")
    lq_text = ""
    if isinstance(lq, dict) and isinstance(lq.get("text"), str):
        lq_text = _truncate(lq["text"], 220)

    lines = []
    lines.append("=== problem_model_v1 ===")
    lines.append(f"status: {status}")
    lines.append(f"turn_index: {turn_index}")
    lines.append(f"user_statements: {stmt_count}")
    lines.append(f"active_hypothesis_id: {pm.get('active_hypothesis_id')}")
    lines.append(f"confidence: {confidence}")

    if inferred:
        lines.append(f"inferred_problem: {inferred}")
    if reframed:
        lines.append(f"reframed_problem: {reframed}")

    if isinstance(contradictions, list) and contradictions:
        lines.append("contradictions:")
        for c in contradictions:
            lines.append(f"  - {_truncate(str(c), 240)}")

    if isinstance(uncertainty, list) and uncertainty:
        lines.append("uncertainty_areas:")
        for u in uncertainty:
            lines.append(f"  - {_truncate(str(u), 240)}")

    if isinstance(hidden, list) and hidden:
        lines.append("hidden_assumptions:")
        for ha in hidden:
            lines.append(f"  - {_truncate(str(ha), 240)}")

    if lq_text:
        lines.append(f"last_question: {lq_text}")

    return "\n".join(lines) + "\n"
