from __future__ import annotations

import json
from pathlib import Path

from extensions.rolepacks.v1_llm.fixture_schema_v1 import parse_fixture_v1

from tests_ext.tools.upgrade_llm_fixtures_to_v1 import main as upgrade_main


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_upgrade_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fx"
    f = fixtures_dir / "a.json"
    legacy = {"kind": "plan", "lang": "en", "tags": ["X"], "notes": ["n1"]}
    _write_json(f, legacy)

    before = f.read_text(encoding="utf-8")

    code = upgrade_main(["--fixtures-dir", str(fixtures_dir)])
    assert code == 0

    after = f.read_text(encoding="utf-8")
    assert after == before


def test_upgrade_apply_modifies_and_validates_v1(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fx"
    f = fixtures_dir / "a.json"

    legacy = {"kind": "plan", "lang": "en", "tags": ["X"], "notes": ["n1"]}
    _write_json(f, legacy)

    code = upgrade_main(["--fixtures-dir", str(fixtures_dir), "--apply"])
    assert code == 0

    upgraded = _read_json(f)
    assert upgraded["fixture_schema_version"] == "fixture_schema_v1"
    assert upgraded["kind"] == "plan"
    assert upgraded["lang"] == "en"
    assert upgraded["tags"] == ["x"]
    assert upgraded["notes"] == ["n1"]

    # Must be schema-valid
    parse_fixture_v1(upgraded)


def test_upgrade_refuses_unknown_schema_version(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fx"
    f = fixtures_dir / "a.json"

    bad = {"fixture_schema_version": "fixture_schema_v999", "kind": "generic", "lang": "unknown"}
    _write_json(f, bad)

    code = upgrade_main(["--fixtures-dir", str(fixtures_dir), "--apply"])
    assert code == 2
