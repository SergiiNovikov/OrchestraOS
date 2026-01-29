"""
Implements: RUNTIME_POLICIES_v0.md, sections 3, 5.2
Implements: IMPLEMENTATION_GUIDELINES_v0.md, sections 3, 8
Scope: Canonical serialization and hashing utilities for Reference Implementation v0.

Runtime intent (v0):
- Provide deterministic, version-stable canonical bytes for hashing/compare/replay.
- MUST NOT introduce semantic “fixups” or best-effort normalization.
- Used ONLY for:
  - artifact hashing
  - determinism_key materialization (via upstream callers)
  - replay/audit comparisons

Canonicalization rules (v0):
- JSON serialization with:
  - UTF-8 encoding
  - sorted object keys
  - no insignificant whitespace
  - strict JSON (no NaN/Infinity)
- Newline normalization is applied ONLY to the serialized byte stream:
  - b"\r\n" -> b"\n"
  - b"\r"   -> b"\n"
  This is an execution-level serialization stability rule (not a semantic rewrite step).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize_json(obj: Any) -> bytes:
    """
    Canonicalize a JSON-serializable object into stable bytes.

    MUST:
    - Be deterministic for equivalent inputs.
    - Be stable within v0 across runs in the same Python major/minor series.
    - Refuse non-JSON-serializable inputs (fail-closed for hashing purposes).

    MUST NOT:
    - Perform semantic normalization (e.g., trimming strings, fixing typos,
      case-folding, rewriting numbers, heuristic conversions).

    Args:
        obj: JSON-serializable Python object (dict/list/str/int/float/bool/None).

    Returns:
        bytes: Canonical UTF-8 encoded JSON representation.

    Raises:
        TypeError: If obj is not JSON-serializable under strict JSON.
        ValueError: If serialization violates strict JSON (e.g., NaN/Infinity).
    """
    # Deterministic JSON:
    # - sort_keys=True ensures stable dict key ordering
    # - separators=(',', ':') removes insignificant whitespace
    # - ensure_ascii=False keeps UTF-8 characters (then encoded to UTF-8 bytes)
    # - allow_nan=False enforces strict JSON (fail-closed)
    serialized_str = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    data = serialized_str.encode("utf-8")

    # Execution-level newline normalization for byte stability.
    # This operates on the serialized byte stream only.
    if b"\r" in data:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    return data


def stable_hash_bytes(data: bytes) -> str:
    """
    Compute a stable cryptographic hash for canonical bytes.

    MUST:
    - Be deterministic.
    - Be stable across runs.

    Args:
        data: Canonical bytes.

    Returns:
        str: Lowercase hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(data).hexdigest()


def artifact_hash(artifact_obj: Any) -> str:
    """
    Compute canonical hash of an artifact object.

    Pipeline:
        artifact_obj -> canonicalize_json -> stable_hash_bytes

    Args:
        artifact_obj: JSON-serializable artifact object.

    Returns:
        str: SHA-256 hex digest of the canonicalized artifact representation.
    """
    return stable_hash_bytes(canonicalize_json(artifact_obj))
