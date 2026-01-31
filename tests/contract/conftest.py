from __future__ import annotations

import copy
from typing import Any, Dict


def deep_copy(x: Any) -> Any:
    return copy.deepcopy(x)


def make_valid_request_envelope_v0(*, mode: str = "platform", maturity: str = "IMMATURE") -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "schema_version": "request_envelope_v0",
        "header": {
            "envelope_id": "env_1",
            "req_id": "req_1",
            "trace_id": "trace_1",
            "created_at": "2026-01-30T00:00:00Z",
            "source": "user",
            "mode": mode,
        },
        "payload_isolation": {
            "baseline_norm": "hello",
            "dialogue_context_included": False,
        },
        "intent": {
            "intent": "test_intent",
        },
        "maturity_gate": {
            "maturity": maturity,
            "reason_code": "R1",
            "recommended_next": "route",
        },
        "consistency": {
            "contradictions_detected": False,
        },
    }

    # Freeze candidate required only for delivery + MATURE
    if mode == "delivery" and maturity == "MATURE":
        env["freeze_candidate"] = {
            "goal": "G",
            "success_criteria": "SC",
            "context": "C",
            "scope_in": "IN",
            "scope_out": "OUT",
            "constraints": "K",
            "acceptance_criteria": "AC",
            "output_format": "OF",
            "freeze_ack": True,
        }

    return env


def make_valid_scoped_request_v0(*, policy_flags: list[str] | None = None) -> Dict[str, Any]:
    sr: Dict[str, Any] = {
        "schema_version": "scoped_request_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1"},
        "input_fingerprint": {"baseline_norm_hash": "hash_bn"},
        "carryover_labels": {
            "intent": "test_intent",
            "maturity": "MATURE",
            "contradictions_detected": False,
        },
        "scope": {
            "scope_class": "SCOPE_A",
            "scope_confidence": 1.0,
            "allowed_contours": ["a"],
            "disallowed_contours": ["b"],
            "required_by_contract": ["c"],
        },
        "handoff": {
            "target_role": "intent_interpreter",
            "handoff_payload": {"baseline_norm": "hello"},
            "notes_for_downstream": ["allowed_contours=a", "required_by_contract=c"],
        },
    }

    if policy_flags is not None:
        sr["carryover_labels"]["policy_flags"] = policy_flags
        if len(policy_flags) > 0:
            sr["scope"]["secondary_scope_class"] = "SECONDARY_A"

    return sr


def make_valid_intent_package_v0() -> Dict[str, Any]:
    return {
        "schema_version": "intent_package_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1"},
        "source_fingerprint": {"baseline_norm_hash": "hash_bn"},
        "intent_definition": {
            "intent_status": "RESOLVED",
            "constraints": {
                "allowed_contours": ["a"],
                "required_by_contract": ["c"],
            },
        },
        "ambiguity_report": {"ambiguous": False},
        "conflict_report": {"conflicts_present": False},
        "handoff": {"target_role": "task_decomposer", "notes_for_downstream": ["constraints_only"]},
    }


def make_valid_task_graph_package_v0() -> Dict[str, Any]:
    return {
        "schema_version": "task_graph_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1"},
        "source_fingerprint": {"baseline_norm_hash": "hash_bn"},
        "task_graph": {
            "tasks": [
                {"task_id": "t1", "description": "d1", "depends_on": []},
                {"task_id": "t2", "description": "d2", "depends_on": ["t1"]},
            ]
        },
        "handoff": {"target_role": "role_orchestrator"},
    }


def make_valid_execution_plan_v0() -> Dict[str, Any]:
    return {
        "schema_version": "execution_plan_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1"},
        "tasks": [
            {"task_id": "t1", "execution_role": "exec_a", "order_index": 0},
            {"task_id": "t2", "execution_role": "exec_b", "order_index": 1},
        ],
    }


def make_valid_task_instruction_v0() -> Dict[str, Any]:
    return {
        "schema_version": "task_instruction_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1", "task_id": "t1"},
        "execution_role": "exec_a",
        "task_description": "do something",
        "depends_on": [],
    }


def make_valid_task_result_v0(*, status: str = "success") -> Dict[str, Any]:
    tr: Dict[str, Any] = {
        "schema_version": "task_result_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1", "task_id": "t1"},
        "execution_role": "exec_a",
        "status": status,
        "output": {"type": "text", "payload": "ok"},
        "errors": [],
    }
    if status == "failure":
        tr["errors"] = [{"code": "E1", "message": "bad"}]
    return tr


def make_valid_task_results_v0() -> Dict[str, Any]:
    return {
        "schema_version": "task_result_set_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1"},
        "results": [{"task_result": make_valid_task_result_v0(status="success")}],
    }


def make_valid_final_response_v0() -> Dict[str, Any]:
    return {
        "schema_version": "final_response_artifact_v0",
        "identity": {"envelope_id": "env_1", "req_id": "req_1", "trace_id": "trace_1"},
        "execution_status": {"status": "success"},
        "results": [{"task_result": make_valid_task_result_v0(status="success")}],
    }
