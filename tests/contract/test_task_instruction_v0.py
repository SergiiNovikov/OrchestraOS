from __future__ import annotations

import pytest

from artifacts.task_instruction_v0 import validate_task_instruction_v0
from tests.contract.conftest import deep_copy, make_valid_task_instruction_v0


def test_accepts_valid_direct_object() -> None:
    ti = make_valid_task_instruction_v0()
    validate_task_instruction_v0(ti)


def test_accepts_valid_wrapper_object() -> None:
    ti = make_valid_task_instruction_v0()
    validate_task_instruction_v0({"task_instruction": ti})


def test_rejects_depends_on_not_list() -> None:
    ti = make_valid_task_instruction_v0()
    bad = deep_copy(ti)
    bad["depends_on"] = "not-a-list"
    with pytest.raises(Exception):
        validate_task_instruction_v0(bad)
