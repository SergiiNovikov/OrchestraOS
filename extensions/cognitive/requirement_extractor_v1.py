from __future__ import annotations

from typing import Any, Dict, List

from extensions.conversation.requirement_model_v1 import default_model, validate_model_fail_closed


def _split_sentences(text: str) -> List[str]:
    t = " ".join(text.strip().split())
    if not t:
        return []
    parts: List[str] = []
    for chunk in t.replace("?", ".").replace("!", ".").split("."):
        c = chunk.strip()
        if c:
            parts.append(c)
    return parts


def extract_requirement_model_v1_from_problem(pm: Dict[str, Any], *, step_index: int = 0) -> Dict[str, Any]:
    model = default_model()

    ah = pm.get("active_hypothesis_id")
    active_h: Dict[str, Any] | None = None
    for h in pm.get("hypotheses", []):
        if isinstance(h, dict) and h.get("id") == ah:
            active_h = h
            break

    text = ""
    if isinstance(active_h, dict):
        text = str(active_h.get("reframed_problem") or active_h.get("inferred_problem") or "")
    text = text.strip()

    sents = _split_sentences(text)
    model["goal"] = sents[0] if sents else (text or None)

    users: List[str] = []
    constraints: List[str] = []

    for st in pm.get("user_statements", []):
        if not isinstance(st, dict):
            continue
        if st.get("role") != "user":
            continue
        t = str(st.get("text") or "").strip()
        if not t:
            continue
        tl = t.lower()

        if ("пользов" in tl) or ("user" in tl) or ("кто " in tl) or ("клиент" in tl) or ("стейк" in tl):
            users.append(t)

        if ("без " in tl) or ("нельзя" in tl) or ("must" in tl) or ("огранич" in tl) or ("immutable" in tl):
            constraints.append(t)

    def _dedup(xs: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for x in xs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    model["users"] = _dedup(users)
    model["constraints"] = _dedup(constraints)

    model["status"] = "ready_for_spec"
    model["last_updated_step"] = int(step_index)

    validate_model_fail_closed(model)
    return model
