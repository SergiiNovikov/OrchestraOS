from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Tuple, Union

try:
    from runtime.canonicalization import canonicalize_json  # type: ignore
except Exception as e:  # fail-closed
    raise RuntimeError("FAILED TO IMPORT runtime.canonicalization.canonicalize_json") from e


PolicyVersion = Literal["m19_cognitive_expander_v1"]
LLMMode = Literal["off", "record", "replay"]
LLMProvider = Literal["stub", "mock", "external", "openai"]
CognitiveMode = Literal["rules", "llm"]


@dataclass(frozen=True)
class CognitiveExpanderConfig:
    policy_version: PolicyVersion = "m19_cognitive_expander_v1"
    cognitive_mode: CognitiveMode = "rules"
    llm_mode: LLMMode = "off"
    llm_provider: LLMProvider = "stub"
    cache_dir: str = ".llm_cache"
    conversation_slice_n: int = 8  # last N turns


BytesOrStr = Union[bytes, str]


def _sha256_hex(data: BytesOrStr) -> str:
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical_slice(conversation_turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Only stable fields. Timestamps / ids are excluded by design (determinism invariant).
    Expected turn schema (stable subset):
      {"role": "user"|"assistant", "text": "..."}
    """
    out: List[Dict[str, Any]] = []
    for t in conversation_turns:
        role = t.get("role")
        text = t.get("text")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(text, str):
            continue
        out.append({"role": role, "text": text})
    return out


def _stable_input_key(
    policy_version: str,
    problem_model_payload: Dict[str, Any],
    conversation_slice: List[Dict[str, Any]],
) -> Tuple[str, BytesOrStr]:
    canonical_payload = {
        "policy_version": policy_version,
        "problem_model": problem_model_payload,
        "conversation_slice": conversation_slice,
    }
    canonical_json = canonicalize_json(canonical_payload)  # NOTE: in this repo returns bytes
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


def _deterministic_rules_baseline(problem_model: Dict[str, Any], conversation_slice: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Rules baseline: NEVER pretends deep understanding.
    It emits conservative hypotheses and produces missing_dimensions + next_question when uncertain.
    """
    text_blob = " ".join([t["text"] for t in conversation_slice if t.get("role") == "user"])
    text_blob_lc = text_blob.lower()

    hypotheses: List[str] = []
    contradictions: List[str] = []
    missing: List[str] = []

    if any(w in text_blob_lc for w in ["падает", "ошибка", "error", "fail", "не работает"]):
        hypotheses.append("Возможно описан симптом (ошибка/сбой), а не стратегическая потребность.")
        missing.append("strategic_goal")
    if any(w in text_blob_lc for w in ["продажи", "выручка", "конверсия", "retention", "рост"]):
        hypotheses.append("Есть признаки бизнес-цели (рост/выручка/конверсия); нужно формализовать измеримость.")
        missing.append("measurable_success")

    if "быстро" in text_blob_lc and "качество" in text_blob_lc and "не важно" in text_blob_lc:
        contradictions.append("Одновременно заявлено 'быстро' и 'качество не важно' — возможен конфликт ожиданий.")

    if "measurable_success" in missing:
        next_q = "Как вы поймёте, что стало лучше: что должно измениться (метрика/сигнал/порог), чтобы вы сказали «Бинго»?"
    elif "strategic_goal" in missing:
        next_q = "Если убрать симптомы, какой бизнес-результат вы хотите получить и почему это важно именно сейчас?"
    else:
        next_q = "Какая одна вещь должна стать иначе, чтобы вы сказали «Бинго/утверждаю»?"

    depth_score = 0.2 if missing else 0.5
    return {
        "hidden_business_goals": hypotheses,
        "conflicts_or_contradictions": contradictions,
        "missing_measurable_metrics": ["measurable_success"] if "measurable_success" in missing else [],
        "real_pain_vs_symptom": ["symptom_vs_need"] if "strategic_goal" in missing else [],
        "missing_dimensions": sorted(set(missing)),
        "next_question": next_q,
        "cognitive_depth_score": depth_score,
    }


def _provider_generate(
    provider: LLMProvider,
    policy_version: str,
    stable_input_key: str,
    canonical_json: BytesOrStr,
) -> Dict[str, Any]:
    """
    No network implementation here.
    'external'/'openai' are allow-listed but NOT implemented (fail-closed),
    because a canonical network client surface for M19 is NOT FOUND IN CODEBASE.
    'stub'/'mock' are deterministic generators keyed by stable_input_key.
    """
    if provider in ("external", "openai"):
        _fail_closed("LLM provider selected but network client surface is NOT FOUND IN CODEBASE")

    seed = stable_input_key[:16]
    return {
        "hidden_business_goals": [f"[{seed}] Возможная скрытая цель: уменьшить издержки/риски через автоматизацию."],
        "conflicts_or_contradictions": [],
        "missing_measurable_metrics": ["measurable_success"],
        "real_pain_vs_symptom": ["symptom_vs_need"],
        "missing_dimensions": ["measurable_success"],
        "next_question": "Какая проверяемая формулировка успеха: какой сигнал/порог означает «Бинго»?",
        "cognitive_depth_score": 0.6,
        "metadata": {
            "provider": provider,
            "policy_version": policy_version,
        },
        "_debug": {
            "stable_input_key": stable_input_key,
            "canonical_json_sha256": _sha256_hex(canonical_json),
        },
    }


def run_cognitive_expander_v1(
    *,
    problem_model_v1: Dict[str, Any],
    conversation_turns: List[Dict[str, Any]],
    cfg: CognitiveExpanderConfig,
) -> Dict[str, Any]:
    """
    Returns replay record schema:
      {
        "stable_input_key": str,
        "policy_version": str,
        "raw_output": Any,
        "parsed_output": Any,
        "metadata": dict
      }
    Replay/record are fail-closed.
    """
    if cfg.cognitive_mode == "llm":
        if cfg.llm_mode == "off":
            _fail_closed("cognitive_mode=llm requires ORCHESTRA_LLM_MODE=record|replay (off is forbidden)")
        if cfg.llm_provider not in ("stub", "mock", "external", "openai"):
            _fail_closed("ORCHESTRA_LLM_PROVIDER not in allow-list")

    sliced = _canonical_slice(conversation_turns[-cfg.conversation_slice_n :])

    stable_key, canonical_json = _stable_input_key(cfg.policy_version, problem_model_v1, sliced)
    cache_path = _cache_path(cfg.cache_dir, stable_key)

    if cfg.cognitive_mode == "rules" or cfg.llm_mode == "off":
        parsed = _deterministic_rules_baseline(problem_model_v1, sliced)
        return {
            "stable_input_key": stable_key,
            "policy_version": cfg.policy_version,
            "raw_output": parsed,
            "parsed_output": parsed,
            "metadata": {"mode": "rules"},
        }

    if cfg.llm_mode == "replay":
        if not os.path.exists(cache_path):
            _fail_closed("REPLAY MISS (cache-only): cognitive_expander_v1")
        rec = _read_json(cache_path)
        if rec.get("stable_input_key") != stable_key:
            _fail_closed("CACHE CORRUPTION: stable_input_key mismatch")
        if rec.get("policy_version") != cfg.policy_version:
            _fail_closed("REPLAY POLICY VERSION MISMATCH")
        return rec

    parsed = _provider_generate(cfg.llm_provider, cfg.policy_version, stable_key, canonical_json)
    rec = {
        "stable_input_key": stable_key,
        "policy_version": cfg.policy_version,
        "raw_output": parsed,
        "parsed_output": parsed,
        "metadata": {"mode": "record", "provider": cfg.llm_provider},
    }
    _atomic_write_json(cache_path, rec)
    return rec
