from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import pytest

from tests_ext.rolepacks._comparison_harness import (
    assert_determinism_n3,
    build_snapshot_record,
)


def _rolepacks_to_compare() -> List[str]:
    packs = ["v1_tz", "v1_rules", "v1_llm"]
    if os.environ.get("INCLUDE_DETERMINISTIC", "").strip() == "1":
        packs.insert(0, "deterministic")
    return packs


def _write_aggregated_snapshot(snapshot: dict, *, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_text_key(text: str) -> str:
    k = (
        text.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("?", "")
        .replace(":", "")
        .replace('"', "")
        .replace("'", "")
    )
    return k or "empty"


@pytest.mark.parametrize(
    "texts",
    [
        [
            "hello",
            "How does determinism work?",
            "Make a plan for Milestone 7",
            "Fix failing pytest tests",
            "Сделай план на 3 шага",
            "Почему падает тест?",
        ]
    ],
)
def test_rolepack_comparison_gates_and_aggregated_snapshot(texts: List[str]) -> None:
    rolepacks = _rolepacks_to_compare()

    inputs = []
    for text in texts:
        records = []
        for rp in rolepacks:
            r1, _r2, _r3 = assert_determinism_n3(text, rolepack=rp)
            records.append(build_snapshot_record(rp, r1))

        inputs.append(
            {
                "text": text,
                "key": _normalize_text_key(text),
                "records": records,
            }
        )

    snapshot = {
        "snapshot_kind": "rolepack_comparison_aggregated",
        "rolepacks": rolepacks,
        "inputs": inputs,
    }

    snap_path = Path("tests_ext") / "_snapshots" / "rolepack_comparison__ALL.json"
    _write_aggregated_snapshot(snapshot, path=snap_path)

    assert snap_path.exists()
    assert snap_path.stat().st_size > 0
