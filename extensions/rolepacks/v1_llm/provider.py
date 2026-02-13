from __future__ import annotations

from typing import Any, Dict, Mapping, Protocol

from validation.schemas import SCHEMA_INTENT_PACKAGE_V0


class ProviderError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def generate_intent(
        self,
        scoped_request_v0: Mapping[str, Any],
        stable_input_key: str,
        canonical_json: str,
    ) -> Dict[str, Any]:
        """
        Must return a dict that is intent_package_v0 schema-valid.
        No network calls in Milestone 11 providers.
        """
        ...


def _extract_baseline_norm(scoped_request: Mapping[str, Any]) -> str:
    hp = scoped_request["handoff"]["handoff_payload"]
    v = hp.get("baseline_norm")
    if not isinstance(v, str):
        raise ProviderError("scoped_request.handoff.handoff_payload.baseline_norm must be a string")
    return v


def _allowed_contours(scoped_request: Mapping[str, Any]) -> list[str]:
    allowed = scoped_request.get("scope", {}).get("allowed_contours")
    if isinstance(allowed, list):
        return [str(x) for x in allowed]
    return ["text"]


def _base_intent_package_template(scoped_request: Mapping[str, Any]) -> Dict[str, Any]:
    identity = scoped_request["identity"]
    baseline_hash = scoped_request["input_fingerprint"]["baseline_norm_hash"]

    return {
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
            "intent_status": "RESOLVED",
            "constraints": {
                "allowed_contours": _allowed_contours(scoped_request),
                "required_by_contract": [],
            },
        },
        "ambiguity_report": {
            "ambiguous": False,
            "ambiguity_reason": None,
        },
        "conflict_report": {
            "conflicts_present": False,
            "conflict_summary": None,
        },
        "handoff": {
            "target_role": "task_decomposer",
            "notes_for_downstream": [],
        },
    }


def _classify_stub(text: str) -> str:
    """
    Deterministic 'LLM-like' classifier stub.
    Returns one of: "question", "plan", "code", "generic"
    """
    t = text.strip().lower()
    if not t:
        return "generic"

    if t.endswith("?") or t.startswith(("how ", "why ", "what ", "when ", "где", "как", "почему", "что", "зачем")):
        return "question"

    if any(x in t for x in ("milestone", "roadmap", "plan", "план", "шаг", "тз", "задач")):
        return "plan"

    if any(x in t for x in ("implement", "code", "fix", "bug", "pytest", "test", "реализ", "код", "почин")):
        return "code"

    return "generic"


class StubProvider:
    """
    Provider = the current v1_llm stub behavior.
    Deterministic, no I/O, no time, no randomness.
    """

    def generate_intent(
        self,
        scoped_request_v0: Mapping[str, Any],
        stable_input_key: str,
        canonical_json: str,
    ) -> Dict[str, Any]:
        baseline_norm = _extract_baseline_norm(scoped_request_v0)
        kind = _classify_stub(baseline_norm)

        tpl = _base_intent_package_template(scoped_request_v0)

        status = "RESOLVED" if baseline_norm.strip() else "AMBIGUOUS"
        tpl["intent_definition"]["intent_status"] = status
        tpl["ambiguity_report"]["ambiguous"] = status != "RESOLVED"
        tpl["ambiguity_report"]["ambiguity_reason"] = ["empty baseline_norm"] if status != "RESOLVED" else None

        notes = [
            f"baseline_norm='{baseline_norm}'",
            f"v1_llm.provider='stub'",
            f"v1_llm.kind='{kind}'",
            f"stable_input_key='{stable_input_key}'",
            f"canonical_intent_input_json='{canonical_json}'",
        ]
        tpl["handoff"]["notes_for_downstream"] = notes
        return tpl


class MockProvider:
    """
    Deterministic "richer" provider (no network).
    Purpose: emulate different behavior from stub while remaining fully deterministic.

    Heuristic:
      - Detect language bucket (ru/en/mixed) via presence of Cyrillic
      - Detect intent kind using stub classifier + extra tags
      - Emit extra structured notes for downstream
    """

    def generate_intent(
        self,
        scoped_request_v0: Mapping[str, Any],
        stable_input_key: str,
        canonical_json: str,
    ) -> Dict[str, Any]:
        baseline_norm = _extract_baseline_norm(scoped_request_v0)
        kind = _classify_stub(baseline_norm)

        # language bucket (deterministic)
        has_cyr = any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in baseline_norm)
        has_lat = any("a" <= ch.lower() <= "z" for ch in baseline_norm)
        if has_cyr and has_lat:
            lang = "mixed"
        elif has_cyr:
            lang = "ru"
        elif has_lat:
            lang = "en"
        else:
            lang = "unknown"

        # extra tags (deterministic)
        t = baseline_norm.strip().lower()
        tags: list[str] = []
        if "pytest" in t or "test" in t or "тест" in t:
            tags.append("testing")
        if "json" in t:
            tags.append("json")
        if "milestone" in t or "этап" in t:
            tags.append("milestone")

        tpl = _base_intent_package_template(scoped_request_v0)

        status = "RESOLVED" if baseline_norm.strip() else "AMBIGUOUS"
        tpl["intent_definition"]["intent_status"] = status
        tpl["ambiguity_report"]["ambiguous"] = status != "RESOLVED"
        tpl["ambiguity_report"]["ambiguity_reason"] = ["empty baseline_norm"] if status != "RESOLVED" else None

        notes = [
            f"baseline_norm='{baseline_norm}'",
            f"v1_llm.provider='mock'",
            f"v1_llm.kind='{kind}'",
            f"v1_llm.lang='{lang}'",
            f"v1_llm.tags={tags}",
            f"stable_input_key='{stable_input_key}'",
            f"canonical_intent_input_json='{canonical_json}'",
        ]
        tpl["handoff"]["notes_for_downstream"] = notes
        return tpl
