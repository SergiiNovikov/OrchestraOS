from __future__ import annotations

from apps.front_cli.adapters import EnvelopeOnlyValidatorV0, build_request_envelope_from_text
from apps.front_cli.config import load_profile


def test_build_request_envelope_from_text_validates_via_runtime_validator_fail_closed() -> None:
    profile = load_profile(None).data  # tz_cli_default + defaults (even if json is empty)
    env = build_request_envelope_from_text("hello world", profile)

    v = EnvelopeOnlyValidatorV0()
    v.validate_input(role_id="scope_resolver", artifact=env)  # must raise on any schema mismatch


def test_builder_is_deterministic_for_same_input() -> None:
    profile = load_profile(None).data
    a = build_request_envelope_from_text("same input", profile)
    b = build_request_envelope_from_text("same input", profile)
    assert a == b
