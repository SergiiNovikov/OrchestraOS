from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from artifacts.request_envelope_v0 import validate_request_envelope_v0
from runtime.determinism import EnvironmentFingerprintV0
from runtime.run_manifest import ManifestSpecEntryV0
from runtime.runner import RoleCallablesV0

from tests.contract.conftest import make_valid_request_envelope_v0


def _stable_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, seed: str, n: int = 8) -> str:
    return f"{prefix}_{_stable_hex(seed)[:n]}"


def build_request_envelope_from_text(text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic RequestEnvelope builder строго по v0 contract helper:
      - base object: make_valid_request_envelope_v0(mode, maturity)
      - overwrite header IDs deterministically from (text + created_at + mode + maturity)
      - set created_at from profile (fixed by default)
      - set payload_isolation.baseline_norm = text
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    mode = str(profile["mode"])
    maturity = str(profile["maturity"])
    created_at = str(profile["created_at"])
    source = str(profile["source"])

    env = make_valid_request_envelope_v0(mode=mode, maturity=maturity)

    seed = f"{text}\n{created_at}\n{mode}\n{maturity}"
    env["header"]["trace_id"] = _stable_id("trace", seed)
    env["header"]["envelope_id"] = _stable_id("env", seed)
    env["header"]["req_id"] = _stable_id("req", seed)
    env["header"]["created_at"] = created_at
    env["header"]["source"] = source
    env["header"]["mode"] = mode

    env["payload_isolation"]["baseline_norm"] = text
    env["payload_isolation"]["dialogue_context_included"] = False

    return env


def validate_envelope_fail_closed(envelope: Dict[str, Any]) -> None:
    """
    Каноническая валидация request_envelope_v0 (fail-closed).
    """
    validate_request_envelope_v0(envelope)


class EnvelopeOnlyValidatorV0:
    """
    Runtime validator для Milestone 0:
      - валидирует только вход в scope_resolver как request_envelope_v0
      - остальное no-op (мы не гадаем про downstream схемы)
    """

    def validate_input(self, *, role_id: str, artifact: Any) -> None:
        if role_id == "scope_resolver":
            if not isinstance(artifact, dict):
                raise TypeError("request_envelope_v0 must be a dict")
            validate_envelope_fail_closed(artifact)

    def validate_output(self, *, role_id: str, artifact: Any) -> None:
        return


def roles_deterministic() -> RoleCallablesV0:
    """
    Детерминированный rolepack без “умной логики” (Milestone 0).
    Берём стиль из determinism tests: каждая стадия возвращает json-serializable mapping.
    """
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
    # Runner requires non-empty tuple; these values are recorded into manifest (spec bundle hash comes from specs_dir bytes).
    return (
        ManifestSpecEntryV0(
            spec_name=str(profile["manifest_spec_name"]),
            spec_version=str(profile["manifest_spec_version"]),
            spec_hash=str(profile["manifest_spec_hash"]),
        ),
    )


def ensure_specs_dir(specs_dir: Path) -> None:
    """
    В точности как в determinism/golden harness:
    runner/determinism fail-closed ожидает два файла по именам:
      - RUNTIME_POLICIES_v0.md
      - IMPLEMENTATION_GUIDELINES_v0.md
    """
    specs_dir.mkdir(parents=True, exist_ok=True)

    # Required by runtime.determinism.compute_policy_fingerprint_from_specs_v0()
    (specs_dir / "RUNTIME_POLICIES_v0.md").write_text("RUNTIME_POLICIES_v0\n", encoding="utf-8")

    # Required by runtime.determinism.compute_guidelines_fingerprint_from_specs_v0()
    (specs_dir / "IMPLEMENTATION_GUIDELINES_v0.md").write_text("IMPLEMENTATION_GUIDELINES_v0\n", encoding="utf-8")

    # Optional entropy for bundle hash (safe, deterministic)
    (specs_dir / "SPEC_A.md").write_text("SPEC_A v0\nline2\n", encoding="utf-8")
    (specs_dir / "SPEC_B.md").write_text("SPEC_B v0\n", encoding="utf-8")