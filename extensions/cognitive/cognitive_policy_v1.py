from __future__ import annotations

from typing import Any, Dict, Optional

POLICY_VERSION = "m18_cognitive_v1"


def _active_hypothesis(pm: Dict[str, Any]) -> Dict[str, Any]:
    ah = pm.get("active_hypothesis_id")
    for h in pm.get("hypotheses", []):
        if isinstance(h, dict) and h.get("id") == ah:
            return h
    raise ValueError("active_hypothesis_id not found")


def stabilization_criteria(pm: Dict[str, Any], *, confidence_threshold: float = 0.8) -> bool:
    if pm.get("status") == "stabilized":
        return True

    h = _active_hypothesis(pm)
    conf = float(h.get("confidence", 0.0))
    contradictions = h.get("contradictions")
    uncertainty = h.get("uncertainty_areas")

    if conf < confidence_threshold:
        return False
    if isinstance(contradictions, list) and len(contradictions) > 0:
        return False
    if isinstance(uncertainty, list) and len(uncertainty) > 0:
        return False
    return True


def decide_next(pm: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if pm.get("status") == "stabilized":
        return None

    lq = pm.get("last_question")
    if isinstance(lq, dict) and isinstance(lq.get("id"), str) and isinstance(lq.get("text"), str):
        return {"id": str(lq["id"]), "text": str(lq["text"])}
    return None
