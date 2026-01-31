from __future__ import annotations

from runtime.canonicalization import artifact_hash


def test_artifact_hash_is_order_invariant_for_mappings() -> None:
    a = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}
    b = {"c": {"x": 1, "y": 2}, "a": 1, "b": 2}
    assert artifact_hash(a) == artifact_hash(b)


def test_artifact_hash_is_sensitive_to_list_order() -> None:
    a = {"items": [1, 2, 3]}
    b = {"items": [3, 2, 1]}
    assert artifact_hash(a) != artifact_hash(b)


def test_artifact_hash_is_stable_across_repeated_calls() -> None:
    obj = {"k": "v", "n": 123, "nested": {"a": [1, 2, 3]}}
    h1 = artifact_hash(obj)
    h2 = artifact_hash(obj)
    assert h1 == h2
