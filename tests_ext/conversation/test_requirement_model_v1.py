from __future__ import annotations

import pytest

from extensions.conversation.requirement_model_v1 import apply_user_answer, default_model, validate_model_fail_closed


def test_apply_user_answer_deterministic_n3() -> None:
    m0 = default_model()
    out1 = apply_user_answer(m0, "goal", "Сделать MVP")
    out2 = apply_user_answer(m0, "goal", "Сделать MVP")
    out3 = apply_user_answer(m0, "goal", "Сделать MVP")
    assert out1 == out2 == out3


def test_validate_fail_closed_on_wrong_types() -> None:
    m = default_model()
    m_bad = {**m, "users": "not-a-list"}  # type: ignore[assignment]
    with pytest.raises(ValueError):
        validate_model_fail_closed(m_bad)  # type: ignore[arg-type]

    m_bad2 = {**m, "goal": ["nope"]}  # type: ignore[assignment]
    with pytest.raises(ValueError):
        validate_model_fail_closed(m_bad2)  # type: ignore[arg-type]
