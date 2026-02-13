from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Optional


_ws_re = re.compile(r"\s+", re.UNICODE)


def _normalize_text(s: str) -> str:
    # Deterministic canonicalization:
    # - strip
    # - collapse whitespace
    # - lowercase
    return _ws_re.sub(" ", s.strip()).lower()


def canonical_intent_input_json(scoped_request: Mapping[str, Any]) -> str:
    """
    Canonical form for stable_input_key:
      - baseline_norm (normalized)
      - allowed_contours (sorted)
      - baseline_norm_hash (optional, if present)
    No prompt/template/raw LLM dependencies.
    """
    # baseline_norm
    hp = scoped_request["handoff"]["handoff_payload"]
    baseline_norm = hp.get("baseline_norm")
    if not isinstance(baseline_norm, str):
        raise TypeError("scoped_request.handoff.handoff_payload.baseline_norm must be a string")

    # allowed_contours
    allowed = scoped_request.get("scope", {}).get("allowed_contours")
    allowed_contours: list[str]
    if isinstance(allowed, list):
        allowed_contours = [str(x) for x in allowed]
    else:
        allowed_contours = ["text"]
    allowed_contours = sorted(allowed_contours)

    # baseline_norm_hash (optional)
    baseline_norm_hash: Optional[str] = None
    fp = scoped_request.get("input_fingerprint")
    if isinstance(fp, dict):
        v = fp.get("baseline_norm_hash")
        if isinstance(v, str) and v:
            baseline_norm_hash = v

    payload = {
        "baseline_norm": _normalize_text(baseline_norm),
        "allowed_contours": allowed_contours,
    }
    if baseline_norm_hash is not None:
        payload["baseline_norm_hash"] = baseline_norm_hash

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_input_key(scoped_request: Mapping[str, Any]) -> str:
    cj = canonical_intent_input_json(scoped_request)
    return hashlib.sha256(cj.encode("utf-8")).hexdigest()
