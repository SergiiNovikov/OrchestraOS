from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict

from extensions.rolepacks.v1_llm.stable_key import canonical_intent_input_json, stable_input_key
from extensions.rolepacks.v1_llm.intent_interpreter import intent_interpreter


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _build_min_scoped_request_for_key(text: str) -> Dict[str, Any]:
    return {
        "schema_version": "scoped_request_v0",
        "identity": {"envelope_id": "env_tool", "req_id": "req_tool", "trace_id": "trace_tool"},
        "input_fingerprint": {"baseline_norm_hash": _sha256_hex(text)},
        "scope": {"allowed_contours": ["text"]},
        "handoff": {"handoff_payload": {"baseline_norm": text}},
    }


def _build_full_scoped_request(text: str) -> Dict[str, Any]:
    # Minimal "full" scoped_request that intent_interpreter accepts & validates.
    return {
        "schema_version": "scoped_request_v0",
        "identity": {"envelope_id": "env1", "req_id": "req1", "trace_id": "trace1"},
        "input_fingerprint": {"baseline_norm_hash": _sha256_hex(text)},
        "carryover_labels": {
            "intent": "test_intent",
            "maturity": "MATURE",
            "contradictions_detected": False,
        },
        "scope": {
            "scope_class": "general",
            "scope_confidence": 1.0,
            "allowed_contours": ["text"],
            "disallowed_contours": [],
            "required_by_contract": [],
        },
        "handoff": {
            "target_role": "intent_interpreter",
            "handoff_payload": {"baseline_norm": text},
            "notes_for_downstream": [],
        },
    }


def test_tool_key_matches_intent_interpreter_off_mode_n3(monkeypatch, tmp_path: Path) -> None:
    # Ensure off-mode (stub) and no cache requirement
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_FIXTURES_DIR", raising=False)
    monkeypatch.setenv("LLM_MODE", "off")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))  # harmless in off

    text = "hello"

    sr_key = _build_min_scoped_request_for_key(text)
    key1 = stable_input_key(sr_key)
    key2 = stable_input_key(sr_key)
    key3 = stable_input_key(sr_key)

    assert key1 == key2 == key3

    # Now ensure intent_interpreter emits the same stable key inside notes (deterministic)
    sr_full = _build_full_scoped_request(text)
    out = intent_interpreter(artifact=sr_full)

    notes = out["handoff"]["notes_for_downstream"]
    assert any(f"stable_input_key='{key1}'" == n for n in notes)

    # Sanity: canonical_json is deterministic too
    cj1 = canonical_intent_input_json(sr_key)
    cj2 = canonical_intent_input_json(sr_key)
    assert cj1 == cj2
