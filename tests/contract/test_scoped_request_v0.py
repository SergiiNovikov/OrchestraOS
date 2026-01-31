from __future__ import annotations

import pytest

from artifacts.scoped_request_v0 import validate_scoped_request_v0
from tests.contract.conftest import deep_copy, make_valid_scoped_request_v0


def test_accepts_valid_direct_object() -> None:
    sr = make_valid_scoped_request_v0()
    validate_scoped_request_v0(sr)


def test_accepts_valid_wrapper_object() -> None:
    sr = make_valid_scoped_request_v0()
    validate_scoped_request_v0({"scoped_request": sr})


def test_rejects_policy_flags_non_empty_requires_secondary_scope_class() -> None:
    sr = make_valid_scoped_request_v0(policy_flags=["FLAG_A"])
    validate_scoped_request_v0(sr)

    bad = deep_copy(sr)
    bad["scope"]["secondary_scope_class"] = None
    with pytest.raises(Exception):
        validate_scoped_request_v0(bad)
