from __future__ import annotations

import pytest

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_rules.intent_interpreter import intent_interpreter


def make_scoped_request(text: str) -> dict:
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


@pytest.mark.parametrize(
    "text",
    [
        "hello",
        "How does determinism work?",
        "Make a plan for Milestone 7",
        "Fix failing pytest tests",
        "Explain this spec",
        "Сделай план на 3 шага",
        "Реализуй intent interpreter",
        "Why does JSON fail?",
        "Implement v1_rules rolepack",
        "Почему падает тест?",
    ],
)
def test_v1_rules_intent_interpreter_golden(text: str) -> None:
    sr = make_scoped_request(text)
    out = intent_interpreter(artifact=sr)

    validate_artifact_v0(artifact=out, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)


def test_v1_rules_intent_interpreter_determinism_n3() -> None:
    sr = make_scoped_request("hello")

    out1 = intent_interpreter(artifact=sr)
    out2 = intent_interpreter(artifact=sr)
    out3 = intent_interpreter(artifact=sr)

    assert out1 == out2 == out3
