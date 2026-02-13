from __future__ import annotations

import pytest

from extensions.architect.architect_v1 import (
    ARCHITECT_POLICY_VERSION,
    stable_architect_input_key,
    validate_architect_output_v1_fail_closed,
)
from extensions.conversation.requirement_model_v1 import apply_user_answer, default_model


def test_stable_architect_input_key_deterministic_n3() -> None:
    m = default_model()
    m = apply_user_answer(m, "goal", "Сделать ТЗ")
    m = apply_user_answer(m, "users", "PM, Engineer")
    m = apply_user_answer(m, "success_criteria", "Есть spec")
    m = apply_user_answer(m, "constraints", "Без сети")

    k1 = stable_architect_input_key(policy_version=ARCHITECT_POLICY_VERSION, model=m)
    k2 = stable_architect_input_key(policy_version=ARCHITECT_POLICY_VERSION, model=m)
    k3 = stable_architect_input_key(policy_version=ARCHITECT_POLICY_VERSION, model=m)
    assert k1 == k2 == k3


def test_validate_architect_output_fail_closed() -> None:
    with pytest.raises(Exception):
        validate_architect_output_v1_fail_closed({"schema_version": "architect_output_v1"})  # missing fields
