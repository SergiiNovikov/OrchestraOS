"""
Implements: TASK_DECOMPOSER_SPEC.md, section "Task Graph Package — Schema v0"

Scope (v0):
- Field-level validation for Task Graph Package v0, and only what is explicitly specified
  in TASK_DECOMPOSER_SPEC.md.
- Fail-closed: any mismatch -> raise (TypeError / ValueError), no coercion, no best-effort.
- No role logic, no runtime orchestration.

Representation note (v0, non-semantic):
- Spec commonly shows wrapper form:
    task_graph_package: { ... }
- To avoid representation drift while staying deterministic, this validator accepts:
    A) wrapper form {"task_graph_package": <task_graph_package object>}
    B) direct task_graph_package object (mapping that contains at least 'schema_version')
  Any other shape is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

from validation.schemas import (
    SCHEMA_TASK_GRAPH_V0,
    fail,
    require_enum_str,
    require_key,
    require_mapping,
    require_optional_str,
    require_str,
)


def _require_list_of_non_empty_str(x: Any, path: str) -> None:
    if not isinstance(x, list):
        raise TypeError(f"{path}: expected list")
    for i, item in enumerate(x):
        require_str(item, f"{path}[{i}]")


def _get_task_graph_object(obj: Any) -> Mapping[str, Any]:
    """
    Accept either:
      - wrapper {"task_graph_package": <mapping>}, or
      - direct task_graph_package object (mapping that contains at least 'schema_version').

    Fail-closed:
    - Any other shape is rejected early with a stable error message.
    """
    root = require_mapping(obj, "task_graph_package")
    if "task_graph_package" in root:
        return require_mapping(root["task_graph_package"], "task_graph_package.task_graph_package")
    # direct form must look like task_graph_package
    if "schema_version" not in root:
        fail("task_graph_package: expected wrapper {'task_graph_package': {...}} or direct object with 'schema_version'")
    return root


def validate_task_graph_v0(obj: Any) -> None:
    """
    Validate Task Graph Package v0.

    Implements: TASK_DECOMPOSER_SPEC.md

    Required sections:
    - schema_version
    - identity
    - source_fingerprint
    - task_graph
    - handoff
    """
    tg = _get_task_graph_object(obj)

    # schema_version (required)
    require_enum_str(
        require_key(tg, "schema_version", "task_graph_package"),
        "task_graph_package.schema_version",
        [SCHEMA_TASK_GRAPH_V0],
    )

    # -----------------------------
    # identity (required; determinism_key optional)
    # -----------------------------
    identity = require_mapping(require_key(tg, "identity", "task_graph_package"), "task_graph_package.identity")
    require_str(require_key(identity, "envelope_id", "task_graph_package.identity"), "task_graph_package.identity.envelope_id")
    require_str(require_key(identity, "req_id", "task_graph_package.identity"), "task_graph_package.identity.req_id")
    require_str(require_key(identity, "trace_id", "task_graph_package.identity"), "task_graph_package.identity.trace_id")
    if "determinism_key" in identity:
        require_optional_str(identity["determinism_key"], "task_graph_package.identity.determinism_key")

    # -----------------------------
    # source_fingerprint (required)
    # -----------------------------
    sf = require_mapping(require_key(tg, "source_fingerprint", "task_graph_package"), "task_graph_package.source_fingerprint")
    require_str(
        require_key(sf, "baseline_norm_hash", "task_graph_package.source_fingerprint"),
        "task_graph_package.source_fingerprint.baseline_norm_hash",
    )

    # -----------------------------
    # task_graph (required)
    # -----------------------------
    graph = require_mapping(require_key(tg, "task_graph", "task_graph_package"), "task_graph_package.task_graph")
    tasks = require_key(graph, "tasks", "task_graph_package.task_graph")

    if not isinstance(tasks, list):
        raise TypeError("task_graph_package.task_graph.tasks: expected list")
    if len(tasks) == 0:
        fail("task_graph_package.task_graph.tasks: must be non-empty list")

    seen_ids: set[str] = set()
    for i, t in enumerate(tasks):
        td = require_mapping(t, f"task_graph_package.task_graph.tasks[{i}]")
        task_id = require_str(
            require_key(td, "task_id", f"task_graph_package.task_graph.tasks[{i}]"),
            f"task_graph_package.task_graph.tasks[{i}].task_id",
        )
        if task_id in seen_ids:
            fail(f"task_graph_package.task_graph.tasks[{i}].task_id: duplicate '{task_id}'")
        seen_ids.add(task_id)

        require_str(
            require_key(td, "description", f"task_graph_package.task_graph.tasks[{i}]"),
            f"task_graph_package.task_graph.tasks[{i}].description",
        )

        deps = require_key(td, "depends_on", f"task_graph_package.task_graph.tasks[{i}]")
        _require_list_of_non_empty_str(deps, f"task_graph_package.task_graph.tasks[{i}].depends_on")

    # -----------------------------
    # handoff (required)
    # -----------------------------
    handoff = require_mapping(require_key(tg, "handoff", "task_graph_package"), "task_graph_package.handoff")
    require_enum_str(
        require_key(handoff, "target_role", "task_graph_package.handoff"),
        "task_graph_package.handoff.target_role",
        ["role_orchestrator"],
    )
