from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class FixtureSchemaError(RuntimeError):
    pass


ALLOWED_KINDS = {"question", "plan", "code", "generic"}
ALLOWED_LANGS = {"ru", "en", "mixed", "unknown"}


def _require_dict(x: Any, *, ctx: str) -> Dict[str, Any]:
    if not isinstance(x, dict):
        raise FixtureSchemaError(f"{ctx} must be an object (dict), got: {type(x).__name__}")
    return x


def _require_str(x: Any, *, ctx: str) -> str:
    if not isinstance(x, str) or not x.strip():
        raise FixtureSchemaError(f"{ctx} must be a non-empty string")
    return x.strip()


def _optional_list_of_str(x: Any, *, ctx: str) -> List[str]:
    if x is None:
        return []
    if not isinstance(x, list):
        raise FixtureSchemaError(f"{ctx} must be a list of strings")
    out: List[str] = []
    for i, it in enumerate(x):
        if not isinstance(it, str):
            raise FixtureSchemaError(f"{ctx}[{i}] must be a string")
        s = it.strip()
        if s:
            out.append(s)
    return out


def _optional_dict(x: Any, *, ctx: str) -> Optional[Dict[str, Any]]:
    if x is None:
        return None
    if not isinstance(x, dict):
        raise FixtureSchemaError(f"{ctx} must be an object (dict) if present")
    return x


@dataclass(frozen=True)
class FixtureV1:
    fixture_schema_version: str
    kind: str
    lang: str
    tags: List[str]
    notes: List[str]
    raw_completion: Optional[str]
    parsed_intent: Optional[Dict[str, Any]]

    def to_summary_fields(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "lang": self.lang,
            "tags": self.tags,
            "notes": self.notes,
        }


def parse_fixture_v1(data: Any) -> FixtureV1:
    d = _require_dict(data, ctx="fixture")

    ver = _require_str(d.get("fixture_schema_version"), ctx="fixture.fixture_schema_version")
    if ver != "fixture_schema_v1":
        raise FixtureSchemaError(
            f"Unsupported fixture_schema_version={ver!r}, expected 'fixture_schema_v1'"
        )

    kind = _require_str(d.get("kind"), ctx="fixture.kind").lower()
    if kind not in ALLOWED_KINDS:
        raise FixtureSchemaError(f"fixture.kind must be one of {sorted(ALLOWED_KINDS)}, got: {kind!r}")

    lang = _require_str(d.get("lang"), ctx="fixture.lang").lower()
    if lang not in ALLOWED_LANGS:
        raise FixtureSchemaError(f"fixture.lang must be one of {sorted(ALLOWED_LANGS)}, got: {lang!r}")

    tags = _optional_list_of_str(d.get("tags"), ctx="fixture.tags")
    tags = [t.lower() for t in tags]

    notes = _optional_list_of_str(d.get("notes"), ctx="fixture.notes")

    raw_completion = d.get("raw_completion")
    if raw_completion is not None and not isinstance(raw_completion, str):
        raise FixtureSchemaError("fixture.raw_completion must be a string if present")

    parsed_intent = _optional_dict(d.get("parsed_intent"), ctx="fixture.parsed_intent")

    return FixtureV1(
        fixture_schema_version=ver,
        kind=kind,
        lang=lang,
        tags=tags,
        notes=notes,
        raw_completion=raw_completion,
        parsed_intent=parsed_intent,
    )
