from __future__ import annotations

import sys
import types
from typing import Any


def ensure_v0_validators_importable() -> None:
    """
    v0 validation.schemas lazy-imports all validators, including:
      from artifacts.task_graph_v0 import validate_task_graph_v0

    In this repo snapshot, artifacts/task_graph_v0.py is absent, while the real validator
    lives in artifacts/task_graph_package_v0.py as validate_task_graph_v0.

    We cannot modify v0, so we provide a runtime shim module "artifacts.task_graph_v0"
    that proxies validate_task_graph_v0 to the real implementation.

    Deterministic, fail-closed: if proxy import fails, shim will raise on use.
    """
    mod_name = "artifacts.task_graph_v0"
    if mod_name in sys.modules:
        return

    shim = types.ModuleType(mod_name)

    try:
        from artifacts.task_graph_package_v0 import validate_task_graph_v0 as real_validate_task_graph_v0
    except Exception as e:  # pragma: no cover
        def real_validate_task_graph_v0(_: Any) -> None:
            raise RuntimeError(
                "Shim could not import artifacts.task_graph_package_v0.validate_task_graph_v0. "
                f"Original error: {e}"
            )

    shim.validate_task_graph_v0 = real_validate_task_graph_v0  # type: ignore[attr-defined]
    sys.modules[mod_name] = shim
