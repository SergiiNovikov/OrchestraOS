from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    # Ensure repo root is importable so `import apps...` works without PYTHONPATH hacks.
    repo_root = Path(__file__).resolve().parents[1]
    p = str(repo_root)
    if p not in sys.path:
        sys.path.insert(0, p)
