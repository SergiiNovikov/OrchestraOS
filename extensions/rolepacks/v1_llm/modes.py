from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from .cache import FileCacheBackend, default_cache_dir


LLMMode = Literal["off", "record", "replay"]


class LLMModeError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMSettings:
    mode: LLMMode
    provider: Optional[str]
    cache_dir: Path


def read_llm_settings_from_env() -> LLMSettings:
    mode_raw = os.environ.get("LLM_MODE", "off").strip().lower()
    if mode_raw not in ("off", "record", "replay"):
        raise LLMModeError(f"Invalid LLM_MODE={mode_raw!r}. Allowed: off, record, replay")

    provider = os.environ.get("LLM_PROVIDER")
    if isinstance(provider, str):
        provider = provider.strip() or None

    cache_override = os.environ.get("LLM_CACHE_DIR")
    if isinstance(cache_override, str) and cache_override.strip():
        cache_dir = Path(cache_override.strip())
    else:
        cache_dir = default_cache_dir()

    mode: LLMMode = mode_raw  # type: ignore[assignment]
    return LLMSettings(mode=mode, provider=provider, cache_dir=cache_dir)


def build_cache_backend(settings: LLMSettings) -> FileCacheBackend:
    return FileCacheBackend(cache_dir=settings.cache_dir)


def require_record_provider_allow_list(settings: LLMSettings) -> None:
    """
    Invariants for Milestone 11:
      - record requires provider
      - provider must be allow-listed in factory ({stub, mock})
    The factory enforces allow-list; here we only enforce "provider is present".
    """
    if settings.mode == "record":
        if settings.provider is None:
            raise LLMModeError("LLM_MODE=record requires LLM_PROVIDER to be set (allowed: stub, mock).")
