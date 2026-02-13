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

    # Rolepack selection (policy input)
    # Supported: "deterministic" (Milestone 0), "v1_tz" (live roles)
    "rolepack": "deterministic",

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
    Accept UTF-8 with BOM (common on Windows).
    """
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    raw = path.read_bytes()
    if raw.strip() == b"":
        return {}

    # Windows PowerShell can write UTF-8 with BOM; accept it.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-8")

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
        else:
            # treat as a profile name under PROFILES_DIR
            if profile.endswith(".json"):
                name = Path(profile).stem
                path = PROFILES_DIR / profile
            else:
                name = profile
                path = PROFILES_DIR / f"{profile}.json"

    data = _load_json(path)

    if not isinstance(data, dict):
        raise ValueError(f"Profile must be a JSON object. Got: {type(data).__name__}")

    merged: Dict[str, Any] = {**DEFAULT_PROFILE, **data}

    # required string fields
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

    rp = merged.get("rolepack")
    if rp is not None and (not isinstance(rp, str) or not rp.strip()):
        raise ValueError(f"Profile field 'rolepack' must be a non-empty string if provided. Got: {rp!r}")

    # normalize work_dir / specs_dir
    work_dir = Path(str(merged["work_dir"]))
    merged["work_dir"] = str(work_dir)

    if merged.get("specs_dir"):
        merged["specs_dir"] = str(Path(str(merged["specs_dir"])))
    else:
        merged["specs_dir"] = str(work_dir / "specs_v0")

    return LoadedProfile(name=name, data=merged)
