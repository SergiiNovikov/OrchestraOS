from __future__ import annotations

from typing import Any, Dict, List, Mapping

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

# Reuse canonical shim from v1_tz so validate_artifact_v0 doesn't crash
# when some artifacts/*_v0.py modules are missing in this repo snapshot.
from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable


class IntentInterpreterRulesError(ValueError):
    pass


def _extract_baseline_norm(scoped_request: Mapping[str, Any]) -> str:
    hp = scoped_request["handoff"]["handoff_payload"]
    v = hp.get("baseline_norm")
    if not isinstance(v, str):
        raise IntentInterpreterRulesError("scoped_request.handoff.handoff_payload.baseline_norm must be a string")
    return v


def _classify_rules(text: str) -> str:
    """Deterministic rules-based classifier.

    Returns one of: "question", "plan", "action", "generic".
    """
    t = text.strip().lower()
    if not t:
        return "generic"

    # Questions
    if t.endswith("?") or t.startswith(
        (
            "how ",
            "why ",
            "what ",
            "when ",
            "where ",
            "who ",
            "which ",
            "как ",
            "почему ",
            "что ",
            "когда ",
            "где ",
            "кто ",
            "зачем ",
        )
    ):
        return "question"

    # Planning
    plan_markers = (
        "plan",
        "roadmap",
        "milestone",
        "steps",
        "strategy",
        "план",
        "дорожн",
        "этап",
        "шаг",
        "стратег",
        "тз",
    )
    if any(m in t for m in plan_markers):
        return "plan"

    # Action / implementation requests
    action_starts = (
        "implement",
        "fix",
        "write",
        "create",
        "build",
        "make ",
        "debug",
        "refactor",
        "реализ",
        "почин",
        "сделай",
        "напиши",
        "создай",
        "собери",
        "построй",
        "исправ",
    )
    if t.startswith(action_starts) or any(m in t for m in ("pytest", "test", "bug", "ошибка", "тест")):
        return "action"

    return "generic"


def intent_interpreter(*, artifact: Mapping[str, Any], **_: Any) -> Dict[str, Any]:
    """v1_rules Intent Interpreter (deterministic, schema-valid).

    Input: scoped_request_v0
    Output: intent_package_v0

    Important:
      - Must call ensure_v0_validators_importable() before validate_artifact_v0()
        to avoid ModuleNotFoundError for missing artifacts modules in this repo snapshot.
    """
    ensure_v0_validators_importable()

    validate_artifact_v0(artifact=artifact, expected_schema_version=SCHEMA_SCOPED_REQUEST_V0)

    # The test harness sometimes passes scoped_request directly; tolerate both shapes.
    sr = artifact.get("scoped_request", artifact)

    identity = sr["identity"]
    baseline_hash = sr["input_fingerprint"]["baseline_norm_hash"]

    baseline_norm = _extract_baseline_norm(sr)
    kind = _classify_rules(baseline_norm)

    intent_status = "RESOLVED" if baseline_norm.strip() else "AMBIGUOUS"

    allowed_contours = sr["scope"].get("allowed_contours")
    if not isinstance(allowed_contours, list):
        allowed_contours = ["text"]

    notes: List[str] = [
        f"baseline_norm='{baseline_norm}'",
        f"v1_rules.kind='{kind}'",
    ]

    intent_package: Dict[str, Any] = {
        "schema_version": SCHEMA_INTENT_PACKAGE_V0,
        "identity": {
            "envelope_id": identity["envelope_id"],
            "req_id": identity["req_id"],
            "trace_id": identity["trace_id"],
        },
        "source_fingerprint": {
            "baseline_norm_hash": baseline_hash,
        },
        "intent_definition": {
            "intent_status": intent_status,
            "constraints": {
                "allowed_contours": allowed_contours,
                "required_by_contract": [],
            },
        },
        "ambiguity_report": {
            "ambiguous": intent_status != "RESOLVED",
            "ambiguity_reason": ["empty baseline_norm"] if intent_status != "RESOLVED" else None,
        },
        "conflict_report": {
            "conflicts_present": False,
            "conflict_summary": None,
        },
        "handoff": {
            "target_role": "task_decomposer",
            "notes_for_downstream": notes,
        },
    }

    validate_artifact_v0(artifact=intent_package, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)
    return intent_package
