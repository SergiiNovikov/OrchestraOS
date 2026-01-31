from __future__ import annotations

import pytest

from artifacts.execution_plan_v0 import validate_execution_plan_v0
from tests.contract.conftest import deep_copy, make_valid_execution_plan_v0


def test_accepts_valid_direct_object() -> None:
    ep = make_valid_execution_plan_v0()
    validate_execution_plan_v0(ep)


def test_accepts_valid_wrapper_object() -> None:
    ep = make_valid_execution_plan_v0()
    validate_execution_plan_v0({"execution_plan": ep})


def test_rejects_duplicate_order_index() -> None:
    ep = make_valid_execution_plan_v0()
    bad = deep_copy(ep)
    bad["tasks"][1]["order_index"] = 0
    with pytest.raises(Exception):
        validate_execution_plan_v0(bad)
