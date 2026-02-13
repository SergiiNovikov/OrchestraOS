from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol


class CacheError(RuntimeError):
    pass


class CacheBackend(Protocol):
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        ...

    def put(self, key: str, artifact: Dict[str, Any]) -> None:
        ...


def _repo_root_from_here() -> Path:
    # extensions/rolepacks/v1_llm/cache.py -> v1_llm -> rolepacks -> extensions -> REPO_ROOT
    return Path(__file__).resolve().parents[3]


def default_cache_dir() -> Path:
    # Repo-local, as fixed by orchestrator:
    # tests_ext/_llm_cache/
    return _repo_root_from_here() / "tests_ext" / "_llm_cache"


@dataclass(frozen=True)
class FileCacheBackend:
    cache_dir: Path

    def _path_for_key(self, key: str) -> Path:
        # Keep filenames safe and deterministic
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            p = self._path_for_key(key)
            if not p.exists():
                return None
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise CacheError(f"Cache entry is not a dict: {p}")
            return data
        except Exception as e:
            raise CacheError(f"Cache get failed for key={key!r}: {e}") from e

    def put(self, key: str, artifact: Dict[str, Any]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            target = self._path_for_key(key)

            # Atomic write: write temp then replace
            tmp = target.with_suffix(".json.tmp")
            payload = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
            tmp.write_text(payload, encoding="utf-8")
            os.replace(str(tmp), str(target))
        except Exception as e:
            raise CacheError(f"Cache put failed for key={key!r}: {e}") from e
