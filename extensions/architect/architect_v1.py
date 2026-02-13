from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from extensions.conversation.requirement_model_v1 import validate_model_fail_closed
from extensions.spec_writer.spec_writer_v1 import canonical_requirement_model_json, source_hash_requirement_model

# v1_llm library layer (record/replay/cache/off)
from extensions.rolepacks.v1_llm.cache import CacheError
from extensions.rolepacks.v1_llm.modes import LLMMode, LLMModeError, build_cache_backend, read_llm_settings_from_env

# OpenAI record-only provider (M17.1)
from extensions.llm.openai_responses_client_v1 import (
    OpenAIClientError,
    call_openai_responses_json_mode_fail_closed,
)

ARCHITECT_POLICY_VERSION = "m17_architect_v1"


class ArchitectError(RuntimeError):
    pass


def stable_architect_input_key(*, policy_version: str, model: Dict[str, Any]) -> str:
    """
    Stable key MUST depend only on stable inputs:
      policy_version + source_hash + canonical_requirement_model_json
    (This is the Milestone 17 contract used by tests_ext.)
    """
    validate_model_fail_closed(model)
    canon = canonical_requirement_model_json(model)
    src_hash = source_hash_requirement_model(model)
    payload = policy_version + "\n" + src_hash + "\n" + canon
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _prompt_for_architect(*, model: Dict[str, Any]) -> str:
    """
    Strict JSON output requested. We still validate fail-closed.
    """
    validate_model_fail_closed(model)
    canon = canonical_requirement_model_json(model)

    schema = {
        "schema_version": "architect_output_v1",
        "title": "str",
        "overview": "str",
        "users": ["str"],
        "scope_in": ["str"],
        "scope_out": ["str"],
        "success_criteria": ["str"],
        "constraints": ["str"],
        "assumptions": ["str"],
        "open_questions": ["str"],
        "acceptance_criteria": ["str"],
        "definition_of_done": ["str"],
    }

    return (
        "You are an Architect & Spec Structurer.\n"
        "Return STRICT JSON only (no markdown, no extra text).\n"
        "Language: match the user's language.\n\n"
        f"INPUT requirement_model_v1 (canonical json):\n{canon}\n\n"
        f"OUTPUT JSON schema (informal):\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        "Rules:\n"
        "- Keep lists as list[str].\n"
        "- open_questions: 0-3 items.\n"
        "- acceptance_criteria must be testable.\n"
        "- definition_of_done must be a checklist.\n"
        "- No additional keys.\n"
    )


def validate_architect_output_v1_fail_closed(out: Dict[str, Any]) -> None:
    if not isinstance(out, dict):
        raise ArchitectError("architect_output_v1 must be a dict")
    if out.get("schema_version") != "architect_output_v1":
        raise ArchitectError("architect_output_v1.schema_version must be 'architect_output_v1'")

    def _req_str(k: str) -> None:
        v = out.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ArchitectError(f"architect_output_v1.{k} must be non-empty str")

    def _req_list_str(k: str) -> None:
        v = out.get(k)
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            raise ArchitectError(f"architect_output_v1.{k} must be list[str]")

    _req_str("title")
    _req_str("overview")
    for k in (
        "users",
        "scope_in",
        "scope_out",
        "success_criteria",
        "constraints",
        "assumptions",
        "open_questions",
        "acceptance_criteria",
        "definition_of_done",
    ):
        _req_list_str(k)


def _stub_architect(model: Dict[str, Any]) -> Dict[str, Any]:
    validate_model_fail_closed(model)
    goal = model.get("goal") if isinstance(model.get("goal"), str) else ""
    title = goal.strip() or "Spec v1 (Draft)"
    overview = goal.strip() or "TBD"

    users = list(model.get("users", []))
    scope_in = list(model.get("scope_in", []))
    scope_out = list(model.get("scope_out", []))
    success = list(model.get("success_criteria", []))
    constraints = list(model.get("constraints", []))
    assumptions = list(model.get("assumptions", []))
    open_q = list(model.get("open_questions", []))[:3]

    acceptance = [f"AC{i+1}: {s}" for i, s in enumerate(success)] if success else []
    dod: List[str] = [
        f"Goal fixed: {title}",
        f"Success criteria count: {len(success)}",
        f"Constraints count: {len(constraints)}",
        "Spec generated deterministically (stub)",
    ]

    out = {
        "schema_version": "architect_output_v1",
        "title": title,
        "overview": overview,
        "users": users,
        "scope_in": scope_in,
        "scope_out": scope_out,
        "success_criteria": success,
        "constraints": constraints,
        "assumptions": assumptions,
        "open_questions": open_q,
        "acceptance_criteria": acceptance,
        "definition_of_done": dod,
    }
    validate_architect_output_v1_fail_closed(out)
    return out


def _mock_architect(model: Dict[str, Any]) -> Dict[str, Any]:
    validate_model_fail_closed(model)
    base = _stub_architect(model)

    if not base["scope_in"]:
        base["scope_in"] = ["Core functionality (MVP)", "Basic UI/UX flows"]
    if not base["scope_out"]:
        base["scope_out"] = ["Non-goals / advanced automation beyond MVP"]

    if not base["assumptions"]:
        base["assumptions"] = ["User has access to required inputs/data", "Target environment supports the workflow"]

    ac: List[str] = []
    for i, s in enumerate(base["success_criteria"]):
        ac.append(f"AC{i+1}: Given the defined inputs, the system satisfies: {s}")
    base["acceptance_criteria"] = ac

    base["definition_of_done"] = [
        "Architecture sections completed",
        f"Acceptance criteria defined: {len(base['acceptance_criteria'])}",
        "Open questions captured (0-3)",
        "Spec saved atomically with status=done",
    ]

    validate_architect_output_v1_fail_closed(base)
    return base


def _openai_architect_record(*, prompt: str) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
    """
    Real OpenAI call (record-only).
    Returns (raw_response_json, output_text, parsed_json_dict).
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert product architect.\n"
                "Return ONLY valid JSON object, no markdown, no extra text.\n"
                "The JSON MUST match exactly architect_output_v1 with keys:\n"
                "schema_version,title,overview,users,scope_in,scope_out,success_criteria,constraints,assumptions,"
                "open_questions,acceptance_criteria,definition_of_done.\n"
                "No additional keys."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    raw_resp, output_text = call_openai_responses_json_mode_fail_closed(
        input_messages=messages,
        temperature=0.0,
        timeout_s=120,
    )

    try:
        parsed = json.loads(output_text)
    except Exception as e:
        raise ArchitectError(f"OpenAI output_text was not JSON: {e}\noutput_text={output_text!r}") from e
    if not isinstance(parsed, dict):
        raise ArchitectError("OpenAI parsed_json must be a dict")

    validate_architect_output_v1_fail_closed(parsed)
    return raw_resp, output_text, parsed


def _provider_generate_architect_output(
    *,
    provider: str,
    model: Dict[str, Any],
    prompt: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns (record_extra_fields, parsed_json).
    record_extra_fields is merged into the cache record for audit (e.g., raw_response).
    """
    p = provider.strip().lower()
    if p == "stub":
        parsed = _stub_architect(model)
        return {"raw_completion": json.dumps(parsed, ensure_ascii=False, sort_keys=True)}, parsed
    if p == "mock":
        parsed = _mock_architect(model)
        return {"raw_completion": json.dumps(parsed, ensure_ascii=False, sort_keys=True)}, parsed
    if p in {"openai", "external"}:
        try:
            raw_resp, output_text, parsed = _openai_architect_record(prompt=prompt)
        except OpenAIClientError as e:
            raise ArchitectError(str(e)) from e
        return {"raw_response": raw_resp, "raw_completion": output_text}, parsed

    raise ArchitectError("Unknown provider for architect. Allowed: stub, mock, openai (external alias).")


@dataclass(frozen=True)
class ArchitectAudit:
    llm_mode: LLMMode
    llm_provider: Optional[str]
    llm_cache_key: str
    architect_policy_version: str


def run_architect_v1(*, model: Dict[str, Any]) -> Tuple[Dict[str, Any], ArchitectAudit]:
    """
    Uses v1_llm modes/cache as a library:
      - record: generate + cache.put
      - replay: cache.get only (cache miss => fail-closed)
      - off: fail-closed (spec_mode=llm requires record/replay)
    """
    validate_model_fail_closed(model)

    settings = read_llm_settings_from_env()
    cache = build_cache_backend(settings)

    policy_version = ARCHITECT_POLICY_VERSION
    key = stable_architect_input_key(policy_version=policy_version, model=model)
    prompt = _prompt_for_architect(model=model)

    if settings.mode == "off":
        raise ArchitectError("Spec LLM mode requires LLM_MODE=record or LLM_MODE=replay (LLM_MODE=off is not allowed).")

    if settings.mode == "replay":
        try:
            cached = cache.get(key)
        except CacheError as e:
            raise ArchitectError(str(e)) from e
        if cached is None:
            raise ArchitectError(f"Replay cache miss for key={key}")
        if not isinstance(cached, dict) or cached.get("schema_version") != "architect_llm_record_v1":
            raise ArchitectError("Invalid cache entry schema for architect_llm_record_v1")
        parsed = cached.get("parsed_json")
        if not isinstance(parsed, dict):
            raise ArchitectError("Cache entry missing parsed_json dict")
        validate_architect_output_v1_fail_closed(parsed)

        audit = ArchitectAudit(
            llm_mode=settings.mode,
            llm_provider=cached.get("provider") if isinstance(cached.get("provider"), str) else settings.provider,
            llm_cache_key=key,
            architect_policy_version=policy_version,
        )
        return parsed, audit

    if settings.mode == "record":
        if settings.provider is None:
            raise LLMModeError("LLM_MODE=record requires LLM_PROVIDER to be set.")

        extra, parsed = _provider_generate_architect_output(provider=settings.provider, model=model, prompt=prompt)
        validate_architect_output_v1_fail_closed(parsed)

        record: Dict[str, Any] = {
            "schema_version": "architect_llm_record_v1",
            "policy_version": policy_version,
            "key": key,
            "mode": "record",
            "provider": settings.provider,
            "prompt": prompt,
            "parsed_json": parsed,
        }
        # extra audit fields (raw_response/raw_completion)
        record.update(extra)

        try:
            cache.put(key, record)
        except CacheError as e:
            raise ArchitectError(str(e)) from e

        audit = ArchitectAudit(
            llm_mode=settings.mode,
            llm_provider=settings.provider,
            llm_cache_key=key,
            architect_policy_version=policy_version,
        )
        return parsed, audit

    raise ArchitectError(f"Unhandled LLM_MODE: {settings.mode!r}")
