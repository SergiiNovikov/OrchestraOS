"""
Implements: RUNTIME_POLICIES_v0.md, sections 4, 5 (determinism_key), 5.2
Implements: IMPLEMENTATION_GUIDELINES_v0.md, section 4 (compute_determinism_key_v0)
Implements: REFERENCE_IMPLEMENTATION_STRUCTURE_v0.md, section 4 (spec_bundle_hash from specs/ mirror)

Scope:
- Compute determinism_key for a run (v0) from strictly allowed sources:
  - primary input (Request Envelope or equivalent primary artifact)
  - spec bundle hash (byte-for-byte mirror under specs/)
  - runtime policy version+hash
  - implementation guidelines version+hash
  - environment fingerprint that may affect output (model/version/tokenizer/runtime)

Rules:
- Determinism MUST be fail-closed: missing required data raises.
- Canonicalization is execution-level stability; MUST NOT rewrite semantic content.
- determinism_key is computed by hashing a canonical JSON payload of the materials below.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from runtime.canonicalization import artifact_hash, canonicalize_json, stable_hash_bytes


@dataclass(frozen=True)
class EnvironmentFingerprintV0:
    """
    Environment fingerprint fields that may affect output generation.

    Aligns with RUN_MANIFEST_SCHEMA_v0.md environment fields and extends slightly
    for reproducibility in the reference implementation.

    Fields:
    - runtime_version: version of this runtime implementation (pinned string)
    - model_id: model identifier
    - model_version: model version (provider-specific or pinned string)
    - tokenizer_version: optional tokenizer version string
    - python_version: optional interpreter version (recommended to pin in deployments)
    """

    runtime_version: str
    model_id: str
    model_version: str
    tokenizer_version: Optional[str] = None
    python_version: Optional[str] = None


@dataclass(frozen=True)
class PolicyFingerprintV0:
    """Policy/guidelines fingerprint: version + content hash."""
    version: str
    content_hash: str


def _sha256_file_bytes(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise ValueError(f"Spec file not found or not a file: {path}")
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def compute_spec_bundle_hash_v0(specs_dir: Path) -> str:
    """
    Compute spec_bundle_hash from the byte-for-byte mirror under specs/.

    Implements repository discipline:
    - specs/ files are copied byte-for-byte and used ONLY for spec_bundle_hash.

    Rule (v0):
    - Hash is computed over a deterministic listing of file names + their byte hashes.
    - Only *.md files are included (as per specs/ structure).
    - Ordering is lexicographic by relative POSIX path.

    Returns:
        str: SHA-256 hex digest of canonicalized spec bundle descriptor.

    Raises:
        ValueError: if specs_dir is missing or contains no *.md files.
    """
    if not specs_dir.exists() or not specs_dir.is_dir():
        raise ValueError(f"specs_dir not found or not a directory: {specs_dir}")

    md_files = sorted(
        [p for p in specs_dir.rglob("*.md") if p.is_file()],
        key=lambda p: p.relative_to(specs_dir).as_posix(),
    )

    if not md_files:
        raise ValueError(f"No *.md specs found under: {specs_dir}")

    bundle_items = []
    for p in md_files:
        rel = p.relative_to(specs_dir).as_posix()
        bundle_items.append(
            {
                "path": rel,
                "sha256": _sha256_file_bytes(p),
            }
        )

    descriptor = {
        "schema_version": "spec_bundle_hash_v0",
        "specs": bundle_items,
    }
    return stable_hash_bytes(canonicalize_json(descriptor))


def compute_policy_fingerprint_from_specs_v0(specs_dir: Path) -> PolicyFingerprintV0:
    """
    Compute Runtime Policies fingerprint from specs/ mirror (RUNTIME_POLICIES_v0.md).

    Raises:
        ValueError if the expected file is missing.
    """
    path = specs_dir / "RUNTIME_POLICIES_v0.md"
    return PolicyFingerprintV0(version="v0", content_hash=_sha256_file_bytes(path))


def compute_guidelines_fingerprint_from_specs_v0(specs_dir: Path) -> PolicyFingerprintV0:
    """
    Compute Implementation Guidelines fingerprint from specs/ mirror (IMPLEMENTATION_GUIDELINES_v0.md).

    Raises:
        ValueError if the expected file is missing.
    """
    path = specs_dir / "IMPLEMENTATION_GUIDELINES_v0.md"
    return PolicyFingerprintV0(version="v0", content_hash=_sha256_file_bytes(path))


def compute_determinism_key_v0(
    *,
    primary_input: Any,
    specs_dir: Path,
    environment: EnvironmentFingerprintV0,
    runtime_policies: Optional[PolicyFingerprintV0] = None,
    implementation_guidelines: Optional[PolicyFingerprintV0] = None,
) -> str:
    """
    Compute determinism_key (v0).

    Allowed sources (RUNTIME_POLICIES_v0.md):
    - primary input (Request Envelope or equivalent primary artifact)
    - specs bundle identifiers/hashes
    - runtime policy version/hash
    - implementation guidelines version/hash
    - environment info that affects output

    This function is the SINGLE normative implementation point for determinism_key_v0.

    Args:
        primary_input: Primary input artifact (JSON-serializable), typically Request Envelope.
        specs_dir: Path to specs/ mirror directory (byte-for-byte canonical docs).
        environment: EnvironmentFingerprintV0.
        runtime_policies: Optional override; if None, computed from specs_dir.
        implementation_guidelines: Optional override; if None, computed from specs_dir.

    Returns:
        str: determinism_key as SHA-256 hex digest.

    Raises:
        ValueError/TypeError: fail-closed on missing or non-serializable inputs.
    """
    if primary_input is None:
        raise ValueError("primary_input is required")
    if specs_dir is None:
        raise ValueError("specs_dir is required")
    if environment is None:
        raise ValueError("environment is required")

    spec_bundle_hash = compute_spec_bundle_hash_v0(specs_dir)

    rp = runtime_policies or compute_policy_fingerprint_from_specs_v0(specs_dir)
    ig = implementation_guidelines or compute_guidelines_fingerprint_from_specs_v0(specs_dir)

    primary_input_hash = artifact_hash(primary_input)

    material: Dict[str, Any] = {
        "schema_version": "determinism_key_material_v0",
        "primary_input_hash": primary_input_hash,
        "spec_bundle_hash": spec_bundle_hash,
        "runtime_policies": {
            "version": rp.version,
            "hash": rp.content_hash,
        },
        "implementation_guidelines": {
            "version": ig.version,
            "hash": ig.content_hash,
        },
        "environment": {
            "runtime_version": environment.runtime_version,
            "model_id": environment.model_id,
            "model_version": environment.model_version,
            "tokenizer_version": environment.tokenizer_version,
            "python_version": environment.python_version,
        },
    }

    return stable_hash_bytes(canonicalize_json(material))


def derive_seed_v0(determinism_key: str) -> int:
    """
    Derive a deterministic uint32 seed from determinism_key.

    Implements: IMPLEMENTATION_GUIDELINES_v0.md, section 4 (seed derived from determinism_key).
    Constraint: fixed rule within v0.

    Rule:
    - determinism_key is expected to be a hex SHA-256 digest (64 hex chars).
    - seed = int(first 8 hex chars, base 16) in range [0, 2^32-1].

    Raises:
        ValueError if determinism_key is not a valid hex digest string.
    """
    if not isinstance(determinism_key, str) or len(determinism_key) < 8:
        raise ValueError("determinism_key must be a hex string with length >= 8")
    try:
        return int(determinism_key[:8], 16)
    except ValueError as e:
        raise ValueError("determinism_key must be a valid hex string") from e


def compute_spec_hashes_v0(specs_dir: Path, spec_filenames: Iterable[str]) -> Dict[str, str]:
    """
    Convenience helper: compute raw byte SHA-256 hashes for a set of spec filenames in specs/.

    This is NOT used to make runtime decisions; it is intended to support:
    - run_manifest.specs[] entries (spec_name/spec_version/spec_hash) downstream.

    Args:
        specs_dir: Path to specs/ mirror.
        spec_filenames: iterable of filenames (e.g., 'FRONT_MANAGER_SPEC.md').

    Returns:
        dict: {filename: sha256_hex}

    Raises:
        ValueError if any requested file is missing.
    """
    out: Dict[str, str] = {}
    for name in spec_filenames:
        p = specs_dir / name
        out[name] = _sha256_file_bytes(p)
    return out
