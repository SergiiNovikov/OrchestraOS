from __future__ import annotations

import pytest

from artifacts.request_envelope_v0 import validate_request_envelope_v0
from tests.contract.conftest import deep_copy, make_valid_request_envelope_v0


def test_accepts_valid_direct_object_platform() -> None:
    env = make_valid_request_envelope_v0(mode="platform", maturity="IMMATURE")
    validate_request_envelope_v0(env)


def test_accepts_valid_wrapper_object() -> None:
    env = make_valid_request_envelope_v0(mode="platform", maturity="IMMATURE")
    validate_request_envelope_v0({"request_envelope": env})


def test_rejects_missing_header() -> None:
    env = make_valid_request_envelope_v0()
    bad = deep_copy(env)
    del bad["header"]
    with pytest.raises(Exception):
        validate_request_envelope_v0(bad)


def test_rejects_dialogue_context_included_true() -> None:
    env = make_valid_request_envelope_v0()
    bad = deep_copy(env)
    bad["payload_isolation"]["dialogue_context_included"] = True
    with pytest.raises(Exception):
        validate_request_envelope_v0(bad)


def test_freeze_candidate_required_when_delivery_and_mature() -> None:
    env = make_valid_request_envelope_v0(mode="delivery", maturity="MATURE")
    # already valid (has freeze_candidate)
    validate_request_envelope_v0(env)

    bad = deep_copy(env)
    del bad["freeze_candidate"]
    with pytest.raises(Exception):
        validate_request_envelope_v0(bad)


def test_freeze_candidate_forbidden_when_not_delivery_mature() -> None:
    env = make_valid_request_envelope_v0(mode="platform", maturity="IMMATURE")
    bad = deep_copy(env)
    bad["freeze_candidate"] = {
        "goal": "G",
        "success_criteria": "SC",
        "context": "C",
        "scope_in": "IN",
        "scope_out": "OUT",
        "constraints": "K",
        "acceptance_criteria": "AC",
        "output_format": "OF",
        "freeze_ack": True,
    }
    with pytest.raises(Exception):
        validate_request_envelope_v0(bad)
