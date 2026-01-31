from __future__ import annotations

import pytest

from artifacts.task_result_set_v0 import validate_task_result_set_v0
from tests.contract.conftest import deep_copy, make_valid_task_results_v0


def test_accepts_valid_direct_object() -> None:
    trs = make_valid_task_results_v0()
    validate_task_result_set_v0(trs)


def test_accepts_valid_wrapper_object() -> None:
    trs = make_valid_task_results_v0()
    validate_task_result_set_v0({"task_results": trs})


def test_rejects_empty_results() -> None:
    trs = make_valid_task_results_v0()
    bad = deep_copy(trs)
    bad["results"] = []
    with pytest.raises(Exception):
        validate_task_result_set_v0(bad)
