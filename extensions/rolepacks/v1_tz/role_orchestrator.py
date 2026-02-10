from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from validation.schemas import (
    SCHEMA_EXECUTION_PLAN_V0,
    SCHEMA_TASK_GRAPH_V0,
    SCHEMA_TASK_INSTRUCTION_V0,
    validate_artifact_v0,
)

from ._v0_validator_shim import ensure_v0_validators_importable


class RoleOrchestratorError(ValueError):
    pass


def _normalize_input(input_artifact: Any, *, artifact: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
    if artifact is not None:
        return artifact
    if isinstance(input_artifact, Mapping):
        return input_artifact
    raise RoleOrchestratorError("role_orchestrator: input artifact must be a mapping")


def _extract_task_graph(task_graph_pkg: Mapping[str, Any]) -> Mapping[str, Any]:
    # Allow wrapper style {"task_graph_package": {...}} or direct artifact
    if "task_graph_package" in task_graph_pkg and isinstance(task_graph_pkg["task_graph_package"], Mapping):
        return task_graph_pkg["task_graph_package"]  # type: ignore[return-value]
    return task_graph_pkg


def _assert_graph_integrity(tasks: List[Mapping[str, Any]]) -> None:
    if len(tasks) == 0:
        raise RoleOrchestratorError("task_graph.tasks must be non-empty")

    ids = [t["task_id"] for t in tasks]
    if len(set(ids)) != len(ids):
        raise RoleOrchestratorError("task_graph.tasks contains duplicate task_id")

    id_set = set(ids)
    for t in tasks:
        deps = t["depends_on"]
        for d in deps:
            if d not in id_set:
                raise RoleOrchestratorError(f"task_graph dependency refers to missing task_id: '{d}'")

    # cycle detection via DFS (deterministic)
    adj = {t["task_id"]: list(t["depends_on"]) for t in tasks}
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def dfs(n: str) -> None:
        if n in visiting:
            raise RoleOrchestratorError("cycle detected in task_graph")
        if n in visited:
            return
        visiting.add(n)
        # deterministic: visit deps in sorted order
        for m in sorted(adj.get(n, [])):
            dfs(m)
        visiting.remove(n)
        visited.add(n)

    for tid in sorted(adj.keys()):
        dfs(tid)


def _topo_order(tasks: List[Mapping[str, Any]]) -> List[str]:
    """
    Deterministic topological sort (Kahn) with tie-break by task_id.
    Edges: dep -> task (task depends_on dep).
    """
    task_ids = [t["task_id"] for t in tasks]
    deps_map = {t["task_id"]: list(t["depends_on"]) for t in tasks}

    in_deg: Dict[str, int] = {tid: 0 for tid in task_ids}
    out_edges: Dict[str, List[str]] = {tid: [] for tid in task_ids}

    for tid, deps in deps_map.items():
        for d in deps:
            out_edges[d].append(tid)
            in_deg[tid] += 1

    # deterministic initial queue
    ready = sorted([tid for tid, deg in in_deg.items() if deg == 0])
    order: List[str] = []

    while ready:
        n = ready.pop(0)
        order.append(n)
        for nxt in sorted(out_edges[n]):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                ready.append(nxt)
                ready.sort()

    if len(order) != len(task_ids):
        raise RoleOrchestratorError("cycle detected in task_graph (topo sort incomplete)")
    return order


def _choose_execution_role(task_description: str) -> str:
    """
    Minimal deterministic mapping of task -> execution_role.
    No enums enforced in v0 validator, but role string must be stable.
    """
    t = task_description.lower()
    if any(x in t for x in ("code", "implement", "реализ", "pytest", "test", "bug", "fix", "код")):
        return "exec_code"
    if any(x in t for x in ("plan", "roadmap", "milestone", "план", "шаг", "задач")):
        return "exec_plan"
    if any(x in t for x in ("explain", "why", "how", "объяс", "почему", "как")):
        return "exec_explain"
    return "exec_generic"


def role_orchestrator(
    input_artifact: Any = None,
    run_context: Any = None,
    *,
    artifact: Optional[Mapping[str, Any]] = None,
    **_: Any,
) -> Dict[str, Any]:
    """
    Live Role Orchestrator (rolepack v1_tz)

    Input:
      - task_graph_v0

    Output (bundle, to fit one-stage-one-output runner contract):
      {
        "execution_plan": <execution_plan_v0>,
        "task_instructions": [<task_instruction_v0>, ...],
      }

    Properties:
      - deterministic
      - fail-closed
      - schema-pure for embedded artifacts
    """
    ensure_v0_validators_importable()

    raw = _normalize_input(input_artifact, artifact=artifact)
    tg_pkg = _extract_task_graph(raw)

    validate_artifact_v0(
        artifact=tg_pkg,
        expected_schema_version=SCHEMA_TASK_GRAPH_V0,
    )

    identity = tg_pkg["identity"]
    baseline_hash = tg_pkg["source_fingerprint"]["baseline_norm_hash"]

    tasks: List[Mapping[str, Any]] = tg_pkg["task_graph"]["tasks"]

    _assert_graph_integrity(tasks)
    order = _topo_order(tasks)

    # index tasks by id for stable lookup
    task_by_id = {t["task_id"]: t for t in tasks}

    # Build execution_plan_v0
    plan_tasks: List[Dict[str, Any]] = []
    for idx, tid in enumerate(order):
        desc = task_by_id[tid]["description"]
        plan_tasks.append(
            {
                "task_id": tid,
                "execution_role": _choose_execution_role(desc),
                "order_index": idx,
            }
        )

    execution_plan: Dict[str, Any] = {
        "schema_version": SCHEMA_EXECUTION_PLAN_V0,
        "identity": {
            "envelope_id": identity["envelope_id"],
            "req_id": identity["req_id"],
            "trace_id": identity["trace_id"],
        },
        "tasks": plan_tasks,
    }

    validate_artifact_v0(
        artifact=execution_plan,
        expected_schema_version=SCHEMA_EXECUTION_PLAN_V0,
    )

    # Build task_instruction_v0 for each task
    task_instructions: List[Dict[str, Any]] = []
    for pt in plan_tasks:
        tid = pt["task_id"]
        t = task_by_id[tid]
        ti: Dict[str, Any] = {
            "schema_version": SCHEMA_TASK_INSTRUCTION_V0,
            "identity": {
                "envelope_id": identity["envelope_id"],
                "req_id": identity["req_id"],
                "trace_id": identity["trace_id"],
                "task_id": tid,
            },
            "execution_role": pt["execution_role"],
            "task_description": t["description"],
            "depends_on": list(t["depends_on"]),
        }
        validate_artifact_v0(
            artifact=ti,
            expected_schema_version=SCHEMA_TASK_INSTRUCTION_V0,
        )
        task_instructions.append(ti)

    # Bundle (not a new v0 schema; embedded artifacts are individually v0-valid)
    return {
        "execution_plan": execution_plan,
        "task_instructions": task_instructions,
        "source_fingerprint": {"baseline_norm_hash": baseline_hash},
        "handoff": {"target_role": "execution_roles"},
    }
