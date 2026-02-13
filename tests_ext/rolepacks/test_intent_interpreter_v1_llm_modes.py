from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import pytest

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_llm.intent_interpreter import IntentInterpreterLLMError, intent_interpreter


def make_scoped_request(text: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_SCOPED_REQUEST_V0,
        "identity": {"envelope_id": "env1", "req_id": "req1", "trace_id": "trace1"},
        "input_fingerprint": {"baseline_norm_hash": "hash123"},
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


def _set_env(monkeypatch: pytest.MonkeyPatch, **vars: str) -> None:
    # Clear relevant vars first for isolation
    for k in ("LLM_MODE", "LLM_PROVIDER", "LLM_CACHE_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k, v in vars.items():
        monkeypatch.setenv(k, v)


def test_v1_llm_mode_off_determinism_n3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, LLM_MODE="off", LLM_CACHE_DIR=str(tmp_path))

    sr = make_scoped_request("hello")

    out1 = intent_interpreter(artifact=sr)
    out2 = intent_interpreter(artifact=sr)
    out3 = intent_interpreter(artifact=sr)

    validate_artifact_v0(artifact=out1, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)
    assert out1 == out2 == out3


def test_v1_llm_mode_replay_cache_miss_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, LLM_MODE="replay", LLM_CACHE_DIR=str(tmp_path))

    sr = make_scoped_request("hello")

    with pytest.raises(IntentInterpreterLLMError):
        intent_interpreter(artifact=sr)


def test_v1_llm_mode_record_stub_then_replay_hit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sr = make_scoped_request("hello")

    # record (stub) -> should write cache
    _set_env(monkeypatch, LLM_MODE="record", LLM_PROVIDER="stub", LLM_CACHE_DIR=str(tmp_path))
    out_record = intent_interpreter(artifact=sr)
    validate_artifact_v0(artifact=out_record, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)

    # replay -> must return exactly the cached artifact
    _set_env(monkeypatch, LLM_MODE="replay", LLM_CACHE_DIR=str(tmp_path))
    out_replay = intent_interpreter(artifact=sr)
    validate_artifact_v0(artifact=out_replay, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)

    assert out_record == out_replay
