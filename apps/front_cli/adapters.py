from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from artifacts.request_envelope_v0 import validate_request_envelope_v0
from runtime.determinism import EnvironmentFingerprintV0
from runtime.run_manifest import ManifestSpecEntryV0
from runtime.runner import RoleCallablesV0


def make_valid_request_envelope_v0(*, mode: str = "platform", maturity: str = "IMMATURE") -> Dict[str, Any]:
    """Production-side builder for a strictly valid request_envelope_v0.

    Canon: apps/ must not import tests/.
    Deterministic: no now()/uuid().
    """
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
        "intent": {"intent": "test_intent"},
        "maturity_gate": {
            "maturity": maturity,
            "reason_code": "R1",
            "recommended_next": "route",
        },
        "consistency": {"contradictions_detected": False},
    }

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

    # Validate immediately: fail-closed if schema drifted
    validate_request_envelope_v0(env)
    return env


def _stable_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, seed: str, n: int = 8) -> str:
    return f"{prefix}_{_stable_hex(seed)[:n]}"


def build_request_envelope_from_text(text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    mode = str(profile["mode"])
    maturity = str(profile["maturity"])
    created_at = str(profile["created_at"])
    source = str(profile["source"])

    env = make_valid_request_envelope_v0(mode=mode, maturity=maturity)

    # IMPORTANT: keep seed stable and consistent with existing v0 harness behavior.
    seed = f"{text}\n{created_at}\n{mode}\n{maturity}"
    env["header"]["trace_id"] = _stable_id("trace", seed)
    env["header"]["envelope_id"] = _stable_id("env", seed)
    env["header"]["req_id"] = _stable_id("req", seed)
    env["header"]["created_at"] = created_at
    env["header"]["source"] = source
    env["header"]["mode"] = mode

    env["payload_isolation"]["baseline_norm"] = text
    env["payload_isolation"]["dialogue_context_included"] = False

    # Validate final envelope: fail-closed
    validate_request_envelope_v0(env)
    return env


def validate_envelope_fail_closed(envelope: Dict[str, Any]) -> None:
    validate_request_envelope_v0(envelope)


class EnvelopeOnlyValidatorV0:
    def validate_input(self, *, role_id: str, artifact: Any) -> None:
        if role_id == "scope_resolver":
            if not isinstance(artifact, dict):
                raise TypeError("request_envelope_v0 must be a dict")
            validate_envelope_fail_closed(artifact)

    def validate_output(self, *, role_id: str, artifact: Any) -> None:
        return


def roles_deterministic() -> RoleCallablesV0:
    def scope_resolver(inp: Any, _ctx: Any) -> Any:
        return {"stage": "scope_resolver", "in": inp}

    def intent_interpreter(inp: Any, _ctx: Any) -> Any:
        return {"stage": "intent_interpreter", "in": inp}

    def task_decomposer(inp: Any, _ctx: Any) -> Any:
        return {"stage": "task_decomposer", "in": inp}

    def role_orchestrator(inp: Any, _ctx: Any) -> Any:
        return {"stage": "role_orchestrator", "in": inp}

    def execution_roles(inp: Any, _ctx: Any) -> Any:
        return {"stage": "execution_roles", "in": inp}

    def result_assembler(inp: Any, _ctx: Any) -> Any:
        return {"stage": "result_assembler", "in": inp}

    return RoleCallablesV0(
        scope_resolver=scope_resolver,
        intent_interpreter=intent_interpreter,
        task_decomposer=task_decomposer,
        role_orchestrator=role_orchestrator,
        execution_roles=execution_roles,
        result_assembler=result_assembler,
    )


def environment_from_profile(profile: Dict[str, Any]) -> EnvironmentFingerprintV0:
    return EnvironmentFingerprintV0(
        runtime_version=str(profile["runtime_version"]),
        model_id=str(profile["model_id"]),
        model_version=str(profile["model_version"]),
        tokenizer_version=str(profile["tokenizer_version"]),
    )


def minimal_specs_from_profile(profile: Dict[str, Any]) -> Tuple[ManifestSpecEntryV0, ...]:
    return (
        ManifestSpecEntryV0(
            spec_name=str(profile["manifest_spec_name"]),
            spec_version=str(profile["manifest_spec_version"]),
            spec_hash=str(profile["manifest_spec_hash"]),
        ),
    )


def ensure_specs_dir(specs_dir: Path) -> None:
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "RUNTIME_POLICIES_v0.md").write_text("RUNTIME_POLICIES_v0\n", encoding="utf-8")
    (specs_dir / "IMPLEMENTATION_GUIDELINES_v0.md").write_text("IMPLEMENTATION_GUIDELINES_v0\n", encoding="utf-8")
    (specs_dir / "SPEC_A.md").write_text("SPEC_A v0\nline2\n", encoding="utf-8")
    (specs_dir / "SPEC_B.md").write_text("SPEC_B v0\n", encoding="utf-8")


def _wrap_role_callable(role_fn):
    def _call(inp: Any, ctx: Any) -> Any:
        return role_fn(artifact=inp, run_context=ctx)

    return _call


def _load_registry(module_path: str) -> Dict[str, Any]:
    mod = importlib.import_module(module_path)
    registry = getattr(mod, "ROLE_REGISTRY", None)
    if not isinstance(registry, dict):
        raise ValueError(f"{module_path} must export ROLE_REGISTRY dict")
    return registry


def roles_from_profile(profile: Dict[str, Any]) -> RoleCallablesV0:
    env_rp = os.environ.get("ORCHESTRA_ROLEPACK")
    rolepack = (
        env_rp.strip()
        if isinstance(env_rp, str) and env_rp.strip()
        else str(profile.get("rolepack", "deterministic"))
    )

    if rolepack == "deterministic":
        return roles_deterministic()

    if rolepack == "v1_tz":
        registry = _load_registry("extensions.rolepacks.v1_tz.registry")

        required = [
            "scope_resolver",
            "intent_interpreter",
            "task_decomposer",
            "role_orchestrator",
            "execution_roles",
            "result_assembler",
        ]
        missing = [r for r in required if r not in registry]
        if missing:
            raise ValueError(f"Rolepack v1_tz is missing required roles: {missing}")

        return RoleCallablesV0(
            scope_resolver=_wrap_role_callable(registry["scope_resolver"]),
            intent_interpreter=_wrap_role_callable(registry["intent_interpreter"]),
            task_decomposer=_wrap_role_callable(registry["task_decomposer"]),
            role_orchestrator=_wrap_role_callable(registry["role_orchestrator"]),
            execution_roles=_wrap_role_callable(registry["execution_roles"]),
            result_assembler=_wrap_role_callable(registry["result_assembler"]),
        )

    if rolepack == "v1_llm":
        tz = _load_registry("extensions.rolepacks.v1_tz.registry")
        llm = _load_registry("extensions.rolepacks.v1_llm.registry")

        required_tz = [
            "scope_resolver",
            "task_decomposer",
            "role_orchestrator",
            "execution_roles",
            "result_assembler",
        ]
        missing_tz = [r for r in required_tz if r not in tz]
        if missing_tz:
            raise ValueError(f"Rolepack v1_tz is missing required roles for v1_llm composition: {missing_tz}")

        if "intent_interpreter" not in llm:
            raise ValueError("Rolepack v1_llm must provide intent_interpreter")

        return RoleCallablesV0(
            scope_resolver=_wrap_role_callable(tz["scope_resolver"]),
            intent_interpreter=_wrap_role_callable(llm["intent_interpreter"]),
            task_decomposer=_wrap_role_callable(tz["task_decomposer"]),
            role_orchestrator=_wrap_role_callable(tz["role_orchestrator"]),
            execution_roles=_wrap_role_callable(tz["execution_roles"]),
            result_assembler=_wrap_role_callable(tz["result_assembler"]),
        )

    if rolepack == "v1_rules":
        tz = _load_registry("extensions.rolepacks.v1_tz.registry")
        rules = _load_registry("extensions.rolepacks.v1_rules.registry")

        required_tz = [
            "scope_resolver",
            "task_decomposer",
            "role_orchestrator",
            "execution_roles",
            "result_assembler",
        ]
        missing_tz = [r for r in required_tz if r not in tz]
        if missing_tz:
            raise ValueError(f"Rolepack v1_tz is missing required roles for v1_rules composition: {missing_tz}")

        if "intent_interpreter" not in rules:
            raise ValueError("Rolepack v1_rules must provide intent_interpreter")

        return RoleCallablesV0(
            scope_resolver=_wrap_role_callable(tz["scope_resolver"]),
            intent_interpreter=_wrap_role_callable(rules["intent_interpreter"]),
            task_decomposer=_wrap_role_callable(tz["task_decomposer"]),
            role_orchestrator=_wrap_role_callable(tz["role_orchestrator"]),
            execution_roles=_wrap_role_callable(tz["execution_roles"]),
            result_assembler=_wrap_role_callable(tz["result_assembler"]),
        )

    raise ValueError(
        f"Unknown rolepack: {rolepack!r}. Supported: 'deterministic', 'v1_tz', 'v1_llm', 'v1_rules'"
    )
