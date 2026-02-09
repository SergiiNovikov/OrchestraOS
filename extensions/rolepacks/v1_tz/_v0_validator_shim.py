from __future__ import annotations

import sys
import types
from typing import Any


def ensure_v0_validators_importable() -> None:
    """
    v0 validate_artifact_v0 lazily imports ALL validators, including artifacts.task_graph_v0.
    In this repo snapshot, artifacts.task_graph_v0 is missing, so validate_artifact_v0 crashes
    before it can validate anything.

    We cannot modify v0. So we provide a runtime-only shim module to satisfy the import.
    Fail-closed: if validate_task_graph_v0 is ever called, we raise.
    """
    mod_name = "artifacts.task_graph_v0"
    if mod_name in sys.modules:
        return

    shim = types.ModuleType(mod_name)

    def validate_task_graph_v0(_: Any) -> None:
        raise RuntimeError(
            "validate_task_graph_v0 was invoked, but artifacts.task_graph_v0 is not present in this repo snapshot. "
            "Fail-closed shim triggered."
        )

    shim.validate_task_graph_v0 = validate_task_graph_v0  # type: ignore[attr-defined]
    sys.modules[mod_name] = shim
