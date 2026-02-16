from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

try:
    from runtime.canonicalization import canonicalize_json  # type: ignore
except Exception as e:
    raise RuntimeError("FAILED TO IMPORT runtime.canonicalization.canonicalize_json") from e


PolicyVersion = Literal["m19_requirement_extractor_v1"]
LLMMode = Literal["off", "record", "replay"]
LLMProvider = Literal["stub", "mock", "external", "openai"]
ExtractionMode = Literal["rules", "llm"]


@dataclass(frozen=True)
class RequirementExtractorConfig:
    policy_version: PolicyVersion = "m19_requirement_extractor_v1"
    extraction_mode: ExtractionMode = "rules"
    llm_mode: LLMMode = "off"
    llm_provider: LLMProvider = "stub"
    cache_dir: str = ".llm_cache"
    conversation_slice_n: int = 8


BytesOrStr = Union[bytes, str]


def _sha256_hex(data: BytesOrStr) -> str:
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical_slice(conversation_turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in conversation_turns:
        role = t.get("role")
        text = t.get("text")
        if role in ("user", "assistant") and isinstance(text, str):
            out.append({"role": role, "text": text})
    return out


def _stable_input_key(
    policy_version: str,
    problem_model_payload: Dict[str, Any],
    cognitive_hypotheses_payload: Optional[Dict[str, Any]],
    conversation_slice: List[Dict[str, Any]],
) -> Tuple[str, BytesOrStr]:
    canonical_payload = {
        "policy_version": policy_version,
        "problem_model": problem_model_payload,
        "cognitive_hypotheses": cognitive_hypotheses_payload or {},
        "conversation_slice": conversation_slice,
    }
    canonical_json = canonicalize_json(canonical_payload)  # NOTE: bytes in this repo
    return _sha256_hex(canonical_json), canonical_json


def _cache_path(cache_dir: str, stable_input_key: str) -> str:
    return os.path.join(cache_dir, f"{stable_input_key}.json")


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
    os.replace(tmp_path, path)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fail_closed(msg: str) -> None:
    raise RuntimeError(msg)


def _rules_judge_and_build(
    problem_model_v1: Dict[str, Any],
    cognitive: Optional[Dict[str, Any]],
    conversation_slice: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # IMPORTANT:
    # Use LAST user message as the primary signal for goal/success.
    # Otherwise earlier generic phrasing ("улучшить процесс") keeps goal_score low forever.
    user_turns: List[str] = [t["text"] for t in conversation_slice if t.get("role") == "user" and isinstance(t.get("text"), str)]
    last_user_text = (user_turns[-1].strip() if user_turns else "")
    all_user_text = " ".join(user_turns).strip()

    goals: List[str] = []
    success: List[str] = []
    constraints: List[str] = []
    open_questions: List[str] = []
    contradictions: List[str] = []

    if cognitive:
        contradictions.extend(cognitive.get("conflicts_or_contradictions", []) or [])
        if cognitive.get("missing_measurable_metrics"):
            open_questions.append("measurable_success")
        if cognitive.get("real_pain_vs_symptom"):
            open_questions.append("strategic_goal")

    # Goal extraction: prefer last user text, fall back to full history if needed
    def _has_goal_marker(s: str) -> bool:
        lc = s.lower()
        markers = ["цель", "хочу", "нужно", "надо", "хотим", "нужна"]
        return any(m in lc for m in markers)

    goal_source = last_user_text if (last_user_text and _has_goal_marker(last_user_text)) else all_user_text
    if goal_source and _has_goal_marker(goal_source):
        goals.append(goal_source[:240])

    # Success extraction: also prefer last user text (where user typically answers the pressure question)
    metric_tokens = [
        "%", "процент", "конверси", "выручк",
        "retention", "nps", "latency", "время",
        "стоимость", "cpa", "roi", "ms",
    ]
    success_source = last_user_text if last_user_text else all_user_text
    has_metric = bool(success_source) and any(tok in success_source.lower() for tok in metric_tokens)

    if has_metric:
        success.append(success_source[:240])
        # If we now have a measurable success signal, clear this open question.
        open_questions = [q for q in open_questions if q != "measurable_success"]
    else:
        open_questions.append("measurable_success")

    open_questions = sorted(set(open_questions))

    return {
        "goals": goals,
        "success_criteria": success,
        "constraints": constraints,
        "open_questions": open_questions,
        "contradictions_detected": bool(contradictions),
        "contradictions": contradictions,
        "source": {
            "used_cognitive_hypotheses": bool(cognitive),
        },
    }


def _provider_generate_variants(
    provider: LLMProvider,
    stable_input_key: str,
    canonical_json: BytesOrStr,
) -> Dict[str, Any]:
    if provider in ("external", "openai"):
        _fail_closed("LLM provider selected but network client surface is NOT FOUND IN CODEBASE")

    seed = stable_input_key[:16]
    return {
        "variants": [
            {
                "goals": [f"[{seed}] Сформулировать стратегическую цель в терминах бизнес-результата."],
                "success_criteria": ["Определить измеримый сигнал успеха (порог/ориентир)."],
                "open_questions": ["measurable_success", "strategic_goal"],
            }
        ],
        "_debug": {
            "stable_input_key": stable_input_key,
            "canonical_json_sha256": _sha256_hex(canonical_json),
        },
    }


def run_requirement_extractor_v1(
    *,
    problem_model_v1: Dict[str, Any],
    cognitive_hypotheses_v1: Optional[Dict[str, Any]],
    conversation_turns: List[Dict[str, Any]],
    cfg: RequirementExtractorConfig,
) -> Dict[str, Any]:
    if cfg.extraction_mode == "llm":
        if cfg.llm_mode == "off":
            _fail_closed("extraction_mode=llm requires ORCHESTRA_LLM_MODE=record|replay (off is forbidden)")
        if cfg.llm_provider not in ("stub", "mock", "external", "openai"):
            _fail_closed("ORCHESTRA_LLM_PROVIDER not in allow-list")

    sliced = _canonical_slice(conversation_turns[-cfg.conversation_slice_n :])
    stable_key, canonical_json = _stable_input_key(cfg.policy_version, problem_model_v1, cognitive_hypotheses_v1, sliced)
    cache_path = _cache_path(cfg.cache_dir, stable_key)

    if cfg.extraction_mode == "rules" or cfg.llm_mode == "off":
        req = _rules_judge_and_build(problem_model_v1, cognitive_hypotheses_v1, sliced)
        return {
            "stable_input_key": stable_key,
            "policy_version": cfg.policy_version,
            "raw_output": req,
            "parsed_output": req,
            "metadata": {"mode": "rules"},
        }

    if cfg.llm_mode == "replay":
        if not os.path.exists(cache_path):
            _fail_closed("REPLAY MISS (cache-only): requirement_extractor_v1")
        rec = _read_json(cache_path)
        if rec.get("stable_input_key") != stable_key:
            _fail_closed("CACHE CORRUPTION: stable_input_key mismatch")
        if rec.get("policy_version") != cfg.policy_version:
            _fail_closed("REPLAY POLICY VERSION MISMATCH")
        return rec

    variants = _provider_generate_variants(cfg.llm_provider, stable_key, canonical_json)
    judged = _rules_judge_and_build(problem_model_v1, cognitive_hypotheses_v1, sliced)
    raw = {"variants": variants.get("variants", []), "judged": judged}
    rec = {
        "stable_input_key": stable_key,
        "policy_version": cfg.policy_version,
        "raw_output": raw,
        "parsed_output": judged,
        "metadata": {"mode": "record", "provider": cfg.llm_provider},
    }
    _atomic_write_json(cache_path, rec)
    return rec
