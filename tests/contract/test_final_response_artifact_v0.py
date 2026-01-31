from __future__ import annotations

import pytest

from artifacts.final_response_artifact_v0 import validate_final_response_artifact_v0
from tests.contract.conftest import deep_copy, make_valid_final_response_v0


def test_accepts_valid_direct_object() -> None:
    fr = make_valid_final_response_v0()
    validate_final_response_artifact_v0(fr)


def test_accepts_valid_wrapper_object() -> None:
    fr = make_valid_final_response_v0()
    validate_final_response_artifact_v0({"final_response": fr})


def test_rejects_empty_results() -> None:
    fr = make_valid_final_response_v0()
    bad = deep_copy(fr)
    bad["results"] = []
    with pytest.raises(Exception):
        validate_final_response_artifact_v0(bad)
