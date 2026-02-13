from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Union

from extensions.rolepacks.v1_llm.modes import LLMSettings

from .cognitive_policy_v1 import POLICY_VERSION
from .cognitive_rules_v1 import run_rules_step
from .settings import CognitiveSettings


# Contract expected by tests_ext:
COGNITIVE_POLICY_VERSION = POLICY_VERSION


class CognitiveLLMError(RuntimeError):
    pass


def canonical_problem_input_json(pm: Dict[str, Any], *, last_n: int = 8) -> str:
    stmts: List[Dict[str, str]] = []
    for st in pm.get("user_statements", []):
        if not isinstance(st, dict):
            continue
        role = st.get("role")
        text = st.get("text")
        if role in {"user", "assistant"} and isinstance(text, str):
            stmts.append({"role": str(role), "text": text.strip()})
    stmts = stmts[-last_n:]

    ah = pm.get("active_hypothesis_id")
    h_snap: Dict[str, Any] = {}
    for h in pm.get("hypotheses", []):
        if isinstance(h, dict) and h.get("id") == ah:
            for k in (
                "id",
                "inferred_problem",
                "reframed_problem",
                "confidence",
                "contradictions",
                "hidden_assumptions",
                "uncertainty_areas",
            ):
                h_snap[k] = h.get(k)
            break

    payload = {
        "policy_version": COGNITIVE_POLICY_VERSION,
        "statements": stmts,
        "active_hypothesis": h_snap,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_cognitive_input_key(*, pm: Dict[str, Any]) -> str:
    cj = canonical_problem_input_json(pm)
    return hashlib.sha256(cj.encode("utf-8")).hexdigest()


def _coerce_llm_settings(settings: Union[CognitiveSettings, LLMSettings]) -> LLMSettings:
    # tests_ext passes CognitiveSettings; apps/front_cli passes LLMSettings (cog.llm).
    if hasattr(settings, "llm"):  # CognitiveSettings
        return getattr(settings, "llm")
    return settings  # type: ignore[return-value]


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise CognitiveLLMError("Cache record must be a JSON object")
    return obj


def run_llm_step(*, pm: Dict[str, Any], settings: Union[CognitiveSettings, LLMSettings]) -> Dict[str, Any]:
    """
    LLM-gated cognitive step.

    tests_ext contract:
      - replay reads {LLM_CACHE_DIR}/{key}.json where record contains 'parsed_json'
      - cache miss must fail-closed (raise)
      - record writes {key}.json (deterministic), provider required

    Returns: cognitive_step_v1 dict (with keys hypothesis/next_question/should_stabilize/stabilize_reason).
    """
    llm = _coerce_llm_settings(settings)

    if llm.mode == "off":
        raise CognitiveLLMError("LLM_MODE=off cannot run llm cognitive step")

    if llm.cache_dir is None:
        raise CognitiveLLMError("LLM cache_dir is required")

    cache_dir = Path(llm.cache_dir)
    key = stable_cognitive_input_key(pm=pm)
    record_path = cache_dir / f"{key}.json"

    if llm.mode == "replay":
        if not record_path.exists():
            raise CognitiveLLMError(f"Replay cache miss for key={key}")

        rec = _read_json(record_path)

        # Validate minimal shape expected by tests
        if rec.get("policy_version") != COGNITIVE_POLICY_VERSION:
            raise CognitiveLLMError("Replay record policy_version mismatch")
        if rec.get("key") != key:
            raise CognitiveLLMError("Replay record key mismatch")

        parsed = rec.get("parsed_json")
        if not isinstance(parsed, dict):
            raise CognitiveLLMError("Replay record missing parsed_json object")

        return parsed

    if llm.mode == "record":
        # Fail-closed: provider required in record
        if llm.provider is None or str(llm.provider).strip() == "":
            raise CognitiveLLMError("LLM_MODE=record requires LLM_PROVIDER")

        step = run_rules_step(pm)

        rec = {
            "schema_version": "cognitive_llm_record_v1",
            "policy_version": COGNITIVE_POLICY_VERSION,
            "key": key,
            "mode": "record",
            "provider": str(llm.provider),
            "prompt": "deterministic_rules_proxy",
            "raw_completion": json.dumps(step, ensure_ascii=False),
            "parsed_json": step,
        }
        cache_dir.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return step

    raise CognitiveLLMError(f"Unhandled LLM_MODE: {llm.mode!r}")
