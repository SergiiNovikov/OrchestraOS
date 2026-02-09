from __future__ import annotations

import pytest

from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

# Must be executed before importing validation.schemas, because validate_artifact_v0
# lazily imports all validators, including artifacts.task_graph_v0 which is missing.
ensure_v0_validators_importable()

from validation.schemas import (  # noqa: E402
    SCHEMA_SCOPED_REQUEST_V0,
    SCHEMA_INTENT_PACKAGE_V0,
    validate_artifact_v0,
)

from extensions.rolepacks.v1_tz.intent_interpreter import intent_interpreter  # noqa: E402


def make_scoped_request(text: str) -> dict:
    """
    Minimal scoped_request_v0 fixture for tests_ext.
    Must remain deterministic and schema-valid.
    """
    return {
        "schema_version": SCHEMA_SCOPED_REQUEST_V0,
        "identity": {
            "envelope_id": "env1",
            "req_id": "req1",
            "trace_id": "trace1",
        },
        "input_fingerprint": {
            "baseline_norm_hash": "hash123",
        },
        "carryover_labels": {
            "intent": "user",
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
            "handoff_payload": {
                "baseline_norm": text,
            },
            "notes_for_downstream": [],
        },
    }


@pytest.mark.parametrize(
    "text",
    [
        "What is OrchestraOS?",
        "Explain the architecture",
        "Generate a plan",
        "Fix determinism bug",
        "Translate this text",
        "Why does validation fail?",
        "Summarize this document",
        "How to add a rolepack?",
        "Describe Milestone 1",
        "What happens next?",
    ],
)
def test_intent_interpreter_golden(text: str) -> None:
    scoped = make_scoped_request(text)

    out = intent_interpreter(artifact=scoped)

    validate_artifact_v0(
        artifact=out,
        expected_schema_version=SCHEMA_INTENT_PACKAGE_V0,
    )


def test_intent_interpreter_determinism_n3() -> None:
    scoped = make_scoped_request("How does determinism work?")

    out1 = intent_interpreter(artifact=scoped)
    out2 = intent_interpreter(artifact=scoped)
    out3 = intent_interpreter(artifact=scoped)

    assert out1 == out2 == out3
