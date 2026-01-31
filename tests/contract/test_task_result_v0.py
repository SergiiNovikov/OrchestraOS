from __future__ import annotations

import pytest

from artifacts.task_result_v0 import validate_task_result_v0
from tests.contract.conftest import deep_copy, make_valid_task_result_v0


def test_accepts_success_with_empty_errors() -> None:
    tr = make_valid_task_result_v0(status="success")
    validate_task_result_v0(tr)


def test_accepts_failure_with_non_empty_errors() -> None:
    tr = make_valid_task_result_v0(status="failure")
    validate_task_result_v0(tr)


def test_rejects_success_with_non_empty_errors() -> None:
    tr = make_valid_task_result_v0(status="success")
    bad = deep_copy(tr)
    bad["errors"] = [{"code": "E1", "message": "should not be here"}]
    with pytest.raises(Exception):
        validate_task_result_v0(bad)


def test_rejects_failure_with_empty_errors() -> None:
    tr = make_valid_task_result_v0(status="failure")
    bad = deep_copy(tr)
    bad["errors"] = []
    with pytest.raises(Exception):
        validate_task_result_v0(bad)
