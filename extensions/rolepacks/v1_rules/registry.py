from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from .intent_interpreter import intent_interpreter

ROLE_REGISTRY: Dict[str, Callable[..., Mapping[str, Any]]] = {
    "intent_interpreter": intent_interpreter,
}
