from __future__ import annotations

import pytest

from artifacts.task_graph_package_v0 import validate_task_graph_v0
from tests.contract.conftest import deep_copy, make_valid_task_graph_package_v0


def test_accepts_valid_direct_object() -> None:
    tg = make_valid_task_graph_package_v0()
    validate_task_graph_v0(tg)


def test_accepts_valid_wrapper_object() -> None:
    tg = make_valid_task_graph_package_v0()
    validate_task_graph_v0({"task_graph_package": tg})


def test_rejects_duplicate_task_id() -> None:
    tg = make_valid_task_graph_package_v0()
    bad = deep_copy(tg)
    bad["task_graph"]["tasks"].append({"task_id": "t1", "description": "dup", "depends_on": []})
    with pytest.raises(Exception):
        validate_task_graph_v0(bad)
