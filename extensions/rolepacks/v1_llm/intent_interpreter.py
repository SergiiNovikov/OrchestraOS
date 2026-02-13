from __future__ import annotations

from typing import Any, Dict, Mapping

from validation.schemas import (
    SCHEMA_INTENT_PACKAGE_V0,
    SCHEMA_SCOPED_REQUEST_V0,
    validate_artifact_v0,
)

# Reuse canonical shim from v1_tz so validate_artifact_v0 doesn't crash
# when some artifacts/*_v0.py modules are missing in this repo snapshot.
from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

from .cache import CacheError
from .modes import LLMModeError, build_cache_backend, read_llm_settings_from_env, require_record_provider_allow_list
from .provider import ProviderError
from .provider_factory import build_provider
from .stable_key import canonical_intent_input_json, stable_input_key


class IntentInterpreterLLMError(ValueError):
    pass


def intent_interpreter(*, artifact: Mapping[str, Any], **_: Any) -> Dict[str, Any]:
    """
    v1_llm Intent Interpreter with LLM-mode scaffold + provider interface (Milestone 11).

    Invariants (do not change):
      - off -> always stub, no cache requirements
      - replay -> cache-only, miss -> fail-closed
      - record -> provider required AND allow-list {stub, mock}, otherwise fail-closed
      - stable_input_key and canonical_json unchanged
      - cache.put atomic + fail-closed
    """
    ensure_v0_validators_importable()
    validate_artifact_v0(artifact=artifact, expected_schema_version=SCHEMA_SCOPED_REQUEST_V0)

    # The harness sometimes passes scoped_request directly; tolerate both shapes.
    sr = artifact.get("scoped_request", artifact)

    # Always compute canonical form + stable key (even in off mode)
    try:
        canon_json = canonical_intent_input_json(sr)
        skey = stable_input_key(sr)
    except Exception as e:
        raise IntentInterpreterLLMError(f"Failed to compute stable_input_key: {e}") from e

    settings = read_llm_settings_from_env()
    cache = build_cache_backend(settings)

    if settings.mode == "replay":
        try:
            cached = cache.get(skey)
        except CacheError as e:
            raise IntentInterpreterLLMError(str(e)) from e

        if cached is None:
            raise IntentInterpreterLLMError(f"LLM_MODE=replay cache miss for key={skey}")

        validate_artifact_v0(artifact=cached, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)
        return cached

    if settings.mode == "record":
        try:
            require_record_provider_allow_list(settings)
            provider = build_provider(settings)  # allow-list enforced inside
        except (LLMModeError, ProviderError) as e:
            raise IntentInterpreterLLMError(str(e)) from e

        # provider generates the intent_package_v0 deterministically (no network in Milestone 11)
        try:
            intent_package = provider.generate_intent(sr, skey, canon_json)
        except Exception as e:
            raise IntentInterpreterLLMError(f"Provider error: {e}") from e

        validate_artifact_v0(artifact=intent_package, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)

        # Write to cache (fail-closed on any error)
        try:
            cache.put(skey, intent_package)
        except CacheError as e:
            raise IntentInterpreterLLMError(str(e)) from e

        return intent_package

    # settings.mode == "off"
    # Invariant: off -> always stub (no cache requirements).
    # We implement this by using StubProvider directly, without requiring LLM_PROVIDER.
    from .provider import StubProvider

    intent_package = StubProvider().generate_intent(sr, skey, canon_json)
    validate_artifact_v0(artifact=intent_package, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)
    return intent_package
