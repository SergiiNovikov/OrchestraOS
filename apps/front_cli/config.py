from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


# repo root = .../reference-implementation-v0
REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "extensions" / "profiles"

DEFAULT_PROFILE: Dict[str, Any] = {
    # determinism: fixed time unless profile overrides
    "created_at": "2026-01-30T00:00:00Z",
    "source": "user",
    "mode": "platform",
    "maturity": "IMMATURE",

    # EnvironmentFingerprintV0 (matches determinism tests defaults)
    "runtime_version": "runtime_v0",
    "model_id": "model_test",
    "model_version": "model_test_v1",
    "tokenizer_version": "tok_v1",

    # Workdir for saving run artifacts (json files)
    "work_dir": str(REPO_ROOT / ".orchestraos"),

    # Specs dir: by default under work_dir/specs_v0
    "specs_dir": None,

    # Minimal manifest specs entry (record-only)
    "manifest_spec_name": "FRONT_MANAGER_SPEC.md",
    "manifest_spec_version": "v0",
    "manifest_spec_hash": "dummy",
}


@dataclass(frozen=True)
class LoadedProfile:
    name: str
    data: Dict[str, Any]


def _load_json(path: Path) -> Dict[str, Any]:
    """
    Load JSON profile.
    Empty file is allowed and treated as {} (defaults-only profile).
    """
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    text = path.read_text(encoding="utf-8")

    # Empty profile is allowed: rely fully on DEFAULT_PROFILE
    if text.strip() == "":
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON profile: {path}. Error: {e}") from e


def load_profile(profile: Optional[str]) -> LoadedProfile:
    """
    profile:
      - None -> extensions/profiles/tz_cli_default.json
      - "tz_cli_default" -> extensions/profiles/tz_cli_default.json
      - "tz_cli_default.json" -> extensions/profiles/tz_cli_default.json
      - "/abs/path/file.json" or "./rel/file.json" -> that file
    """
    if profile is None:
        path = PROFILES_DIR / "tz_cli_default.json"
        name = "tz_cli_default"
    else:
        p = Path(profile)
        if (p.is_absolute() or p.exists()) and p.suffix.lower() == ".json":
            path = p
            name = p.stem
        elif p.is_absolute():
            path = p
            name = p.stem
        else:
            filename = profile if profile.endswith(".json") else f"{profile}.json"
            path = PROFILES_DIR / filename
            name = Path(filename).stem

    raw = _load_json(path)

    # merge defaults → profile overrides
    merged = dict(DEFAULT_PROFILE)
    merged.update(raw or {})

    # fail-closed minimal sanity
    for k in ("created_at", "source", "mode", "maturity"):
        v = merged.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(
                f"Profile field '{k}' must be a non-empty string. Got: {v!r}"
            )

    for k in ("runtime_version", "model_id", "model_version", "tokenizer_version"):
        v = merged.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(
                f"Profile field '{k}' must be a non-empty string. Got: {v!r}"
            )

    # normalize work_dir / specs_dir
    work_dir = Path(str(merged["work_dir"]))
    merged["work_dir"] = str(work_dir)

    if merged.get("specs_dir"):
        merged["specs_dir"] = str(Path(str(merged["specs_dir"])))
    else:
        merged["specs_dir"] = str(work_dir / "specs_v0")

    return LoadedProfile(name=name, data=merged)
