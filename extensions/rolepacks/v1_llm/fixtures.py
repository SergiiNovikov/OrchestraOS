from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class FixturesError(RuntimeError):
    pass


def _repo_root_from_here() -> Path:
    # extensions/rolepacks/v1_llm/fixtures.py -> v1_llm -> rolepacks -> extensions -> REPO_ROOT
    return Path(__file__).resolve().parents[3]


def default_fixtures_dir() -> Path:
    # Repo-local, as fixed by orchestrator:
    # tests_ext/_llm_fixtures/
    return _repo_root_from_here() / "tests_ext" / "_llm_fixtures"


@dataclass(frozen=True)
class FixturesStore:
    fixtures_dir: Path

    def path_for_key(self, stable_key: str) -> Path:
        # Prefer json fixtures
        return self.fixtures_dir / f"{stable_key}.json"

    def read_fixture(self, stable_key: str) -> Dict[str, Any]:
        p = self.path_for_key(stable_key)
        if not p.exists():
            raise FixturesError(f"Fixture missing for key={stable_key}: {p}")

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            raise FixturesError(f"Fixture read/parse failed for key={stable_key}: {e}") from e

        if not isinstance(data, dict):
            raise FixturesError(f"Fixture must be a JSON object (dict), got: {type(data)} at {p}")

        return data


def read_fixtures_dir_from_env() -> Path:
    override = os.environ.get("LLM_FIXTURES_DIR")
    if isinstance(override, str) and override.strip():
        return Path(override.strip())
    return default_fixtures_dir()
