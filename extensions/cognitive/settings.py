from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from extensions.rolepacks.v1_llm.modes import LLMSettings, read_llm_settings_from_env

CognitiveMode = Literal["auto", "rules", "llm"]


@dataclass(frozen=True)
class CognitiveSettings:
    mode: CognitiveMode
    llm: LLMSettings


def read_cognitive_settings_from_env() -> CognitiveSettings:
    raw = os.environ.get("ORCHESTRA_COGNITIVE_MODE", "auto").strip().lower()
    if raw not in {"auto", "rules", "llm"}:
        raise ValueError("Invalid ORCHESTRA_COGNITIVE_MODE. Allowed: auto, rules, llm")

    llm = read_llm_settings_from_env()
    mode: CognitiveMode = raw  # type: ignore[assignment]
    if mode == "auto":
        mode = "llm" if llm.mode in {"record", "replay"} else "rules"
    return CognitiveSettings(mode=mode, llm=llm)
