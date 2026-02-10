from __future__ import annotations

from typing import Dict, Callable, Any, Mapping

from .intent_interpreter import intent_interpreter
from .task_decomposer import task_decomposer
from .role_orchestrator import role_orchestrator
from .execution_roles import execution_roles

ROLE_REGISTRY: Dict[str, Callable[..., Mapping[str, Any]]] = {
    "intent_interpreter": intent_interpreter,
    "task_decomposer": task_decomposer,
    "role_orchestrator": role_orchestrator,
    "execution_roles": execution_roles,
}
