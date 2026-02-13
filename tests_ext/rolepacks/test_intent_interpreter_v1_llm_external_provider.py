from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_llm.intent_interpreter import IntentInterpreterLLMError, intent_interpreter
from extensions.rolepacks.v1_llm.stable_key import stable_input_key


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
    for k in ("LLM_MODE", "LLM_PROVIDER", "LLM_CACHE_DIR", "LLM_FIXTURES_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k, v in vars.items():
        monkeypatch.setenv(k, v)


def _write_fixture(fixtures_dir: Path, key: str, payload: Dict[str, Any]) -> None:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / f"{key}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_record_external_success_then_replay_hit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"

    sr = make_scoped_request("hello")
    key = stable_input_key(sr)

    _write_fixture(
        fixtures_dir,
        key,
        {
            "fixture_schema_version": "fixture_schema_v1",
            "kind": "plan",
            "lang": "en",
            "tags": ["testing"],
            "notes": ["fixture_note_1"],
            "raw_completion": "raw",
            "parsed_intent": {"kind": "plan"},
        },
    )

    _set_env(
        monkeypatch,
        LLM_MODE="record",
        LLM_PROVIDER="external",
        LLM_CACHE_DIR=str(cache_dir),
        LLM_FIXTURES_DIR=str(fixtures_dir),
    )
    out_record = intent_interpreter(artifact=sr)
    validate_artifact_v0(artifact=out_record, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)

    _set_env(monkeypatch, LLM_MODE="replay", LLM_CACHE_DIR=str(cache_dir))
    out_replay = intent_interpreter(artifact=sr)
    validate_artifact_v0(artifact=out_replay, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)

    assert out_record == out_replay


def test_record_external_fixture_missing_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"

    sr = make_scoped_request("hello")

    _set_env(
        monkeypatch,
        LLM_MODE="record",
        LLM_PROVIDER="external",
        LLM_CACHE_DIR=str(cache_dir),
        LLM_FIXTURES_DIR=str(fixtures_dir),
    )

    with pytest.raises(IntentInterpreterLLMError):
        intent_interpreter(artifact=sr)


def test_record_external_fixture_malformed_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"

    sr = make_scoped_request("hello")
    key = stable_input_key(sr)

    # malformed: missing fixture_schema_version + missing kind
    _write_fixture(fixtures_dir, key, {"lang": "en"})

    _set_env(
        monkeypatch,
        LLM_MODE="record",
        LLM_PROVIDER="external",
        LLM_CACHE_DIR=str(cache_dir),
        LLM_FIXTURES_DIR=str(fixtures_dir),
    )

    with pytest.raises(IntentInterpreterLLMError):
        intent_interpreter(artifact=sr)
