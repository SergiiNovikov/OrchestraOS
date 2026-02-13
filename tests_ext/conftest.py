from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    # Ensure repo root is importable so `import apps...` works without PYTHONPATH hacks.
    repo_root = Path(__file__).resolve().parents[1]
    p = str(repo_root)
    if p not in sys.path:
        sys.path.insert(0, p)

    # Install v0 validator shim for all ext-tests (v0 zone is immutable).
    # This prevents ModuleNotFoundError for missing artifacts/*_v0.py modules in this repo snapshot
    # when validate_artifact_v0() lazily imports the full validator set.
    from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

    ensure_v0_validators_importable()
