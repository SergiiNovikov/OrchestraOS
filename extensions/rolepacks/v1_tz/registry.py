from __future__ import annotations

from typing import Dict, Callable, Any, Mapping

from .scope_resolver import scope_resolver
from .intent_interpreter import intent_interpreter
from .task_decomposer import task_decomposer
from .role_orchestrator import role_orchestrator
from .execution_roles import execution_roles
from .result_assembler import result_assembler

ROLE_REGISTRY: Dict[str, Callable[..., Mapping[str, Any]]] = {
    "scope_resolver": scope_resolver,
    "intent_interpreter": intent_interpreter,
    "task_decomposer": task_decomposer,
    "role_orchestrator": role_orchestrator,
    "execution_roles": execution_roles,
    "result_assembler": result_assembler,
}
