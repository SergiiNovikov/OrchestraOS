from __future__ import annotations

from extensions.conversation.requirement_model_v1 import apply_user_answer, default_model
from extensions.spec_writer.spec_writer_v1 import (
    build_spec_document_v1,
    canonical_requirement_model_json,
    source_hash_requirement_model,
)


def test_spec_writer_v1_deterministic_n3() -> None:
    m = default_model()
    m = apply_user_answer(m, "goal", "Сделать виртуального бухгалтера")
    m = apply_user_answer(m, "users", "Предприятия, бухгалтер")
    m = apply_user_answer(m, "success_criteria", "Пачка счетов -> проводки")
    m = apply_user_answer(m, "constraints", "Без сети, минимальный бюджет")

    h1 = source_hash_requirement_model(m)
    h2 = source_hash_requirement_model(m)
    h3 = source_hash_requirement_model(m)
    assert h1 == h2 == h3

    c1 = canonical_requirement_model_json(m)
    c2 = canonical_requirement_model_json(m)
    assert c1 == c2

    d1 = build_spec_document_v1(model=m, conversation_id="abc")
    d2 = build_spec_document_v1(model=m, conversation_id="abc")
    assert d1 == d2
    assert d1["schema_version"] == "spec_document_v1"
    assert d1["format"] == "markdown"
    assert isinstance(d1["title"], str) and d1["title"].strip()
    assert isinstance(d1["content"], str) and "Definition of Done" in d1["content"]

    gen = d1["generated_from"]
    assert gen["conversation_id"] == "abc"
    assert gen["requirement_model_version"] == "requirement_model_v1"
    assert gen["source_hash"] == h1
