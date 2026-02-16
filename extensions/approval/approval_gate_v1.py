from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ApprovalGateConfig:
    approval_required: bool = True
    tokens: List[str] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.tokens is None:
            object.__setattr__(self, "tokens", ["approved", "утверждаю", "согласовано"])


def is_approved_v1(user_text: str, cfg: ApprovalGateConfig = ApprovalGateConfig()) -> bool:
    if not cfg.approval_required:
        return True
    t = (user_text or "").strip().lower()
    return any(tok in t for tok in cfg.tokens)


def apply_approval_gate_v1(
    *,
    user_text: str,
    state: Dict,
    cfg: ApprovalGateConfig = ApprovalGateConfig(),
) -> Dict:
    approved = is_approved_v1(user_text, cfg)
    out = dict(state)
    out["approval_required"] = cfg.approval_required
    out["is_approved"] = approved
    if approved:
        out["status"] = "approved_for_spec"
    return out
