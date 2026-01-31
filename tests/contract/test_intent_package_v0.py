from __future__ import annotations

import pytest

from artifacts.intent_package_v0 import validate_intent_package_v0
from tests.contract.conftest import deep_copy, make_valid_intent_package_v0


def test_accepts_valid_direct_object() -> None:
    ip = make_valid_intent_package_v0()
    validate_intent_package_v0(ip)


def test_accepts_valid_wrapper_object() -> None:
    ip = make_valid_intent_package_v0()
    validate_intent_package_v0({"intent_package": ip})


def test_rejects_missing_constraints() -> None:
    ip = make_valid_intent_package_v0()
    bad = deep_copy(ip)
    del bad["intent_definition"]["constraints"]
    with pytest.raises(Exception):
        validate_intent_package_v0(bad)
