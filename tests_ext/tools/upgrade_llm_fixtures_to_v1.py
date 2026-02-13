from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from extensions.rolepacks.v1_llm.fixtures import default_fixtures_dir
from extensions.rolepacks.v1_llm.fixture_schema_v1 import (
    ALLOWED_KINDS,
    ALLOWED_LANGS,
    FixtureSchemaError,
    parse_fixture_v1,
)


class UpgradeError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise UpgradeError(f"Failed to read/parse JSON: {path} ({e})") from e


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _is_dict(x: Any) -> bool:
    return isinstance(x, dict)


def _ensure_str_or_default(v: Any, default: str) -> str:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


def _ensure_list_of_str(v: Any) -> List[str]:
    if v is None:
        return []
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for it in v:
        if isinstance(it, str) and it.strip():
            out.append(it.strip())
    return out


def _upgrade_payload_to_v1(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upgrades an old/legacy fixture dict to fixture_schema_v1.
    Fail-closed if:
      - fixture_schema_version exists but is not 'fixture_schema_v1'
    """
    ver = payload.get("fixture_schema_version")
    if ver is None:
        payload["fixture_schema_version"] = "fixture_schema_v1"
    else:
        if not isinstance(ver, str):
            raise UpgradeError("fixture_schema_version exists but is not a string")
        if ver != "fixture_schema_v1":
            raise UpgradeError(f"Unsupported fixture_schema_version={ver!r} (refuse to auto-upgrade)")

    # kind/lang defaults
    kind = _ensure_str_or_default(payload.get("kind"), "generic").lower()
    if kind not in ALLOWED_KINDS:
        kind = "generic"
    payload["kind"] = kind

    lang = _ensure_str_or_default(payload.get("lang"), "unknown").lower()
    if lang not in ALLOWED_LANGS:
        lang = "unknown"
    payload["lang"] = lang

    # tags/notes normalize
    payload["tags"] = [t.lower() for t in _ensure_list_of_str(payload.get("tags"))]
    payload["notes"] = _ensure_list_of_str(payload.get("notes"))

    # keep raw_completion / parsed_intent if present, but normalize obvious bad types
    if "raw_completion" in payload and payload["raw_completion"] is not None and not isinstance(payload["raw_completion"], str):
        payload["raw_completion"] = str(payload["raw_completion"])

    if "parsed_intent" in payload and payload["parsed_intent"] is not None and not isinstance(payload["parsed_intent"], dict):
        # Fail-closed would be too strict for migration; safer to drop invalid parsed_intent.
        payload["parsed_intent"] = None

    # Final gate: must parse as v1 (fail-closed, stable errors)
    try:
        parse_fixture_v1(payload)
    except FixtureSchemaError as e:
        raise UpgradeError(f"Upgraded payload still invalid under fixture_schema_v1: {e}") from e

    return payload


@dataclass(frozen=True)
class FileReport:
    path: str
    status: str  # "unchanged" | "upgraded" | "error"
    message: Optional[str] = None


def _iter_fixture_files(fixtures_dir: Path) -> List[Path]:
    if not fixtures_dir.exists():
        return []
    return sorted([p for p in fixtures_dir.glob("*.json") if p.is_file()])


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bulk-upgrade v1_llm external fixtures to fixture_schema_v1.")
    ap.add_argument(
        "--fixtures-dir",
        default=None,
        help="Directory with fixtures (*.json). Default: tests_ext/_llm_fixtures/",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes. Default is dry-run (no writes).",
    )
    ap.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing other files even if one fails.",
    )
    args = ap.parse_args(argv)

    fixtures_dir = Path(args.fixtures_dir) if args.fixtures_dir else default_fixtures_dir()
    files = _iter_fixture_files(fixtures_dir)

    reports: List[FileReport] = []
    changed = 0
    errors = 0

    for p in files:
        try:
            data = _read_json(p)
            if not _is_dict(data):
                raise UpgradeError(f"Fixture must be a JSON object (dict), got: {type(data).__name__}")

            # If already valid v1, leave unchanged (but also validate to catch silent drift)
            if data.get("fixture_schema_version") == "fixture_schema_v1":
                # validate existing
                parse_fixture_v1(data)
                reports.append(FileReport(path=str(p), status="unchanged"))
                continue

            upgraded = _upgrade_payload_to_v1(dict(data))  # copy
            reports.append(FileReport(path=str(p), status="upgraded"))
            changed += 1

            if args.apply:
                text = json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n"
                _atomic_write_text(p, text)

        except Exception as e:
            errors += 1
            reports.append(FileReport(path=str(p), status="error", message=str(e)))
            if not args.continue_on_error:
                break

    out = {
        "fixtures_dir": str(fixtures_dir),
        "mode": "apply" if args.apply else "dry_run",
        "files_total": len(files),
        "files_upgraded": changed,
        "files_errors": errors,
        "reports": [r.__dict__ for r in reports],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    # Exit code: 0 if no errors; 2 if any errors
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
