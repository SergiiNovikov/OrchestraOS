from __future__ import annotations

from .external_provider import ExternalProvider
from .modes import LLMSettings
from .provider import LLMProvider, MockProvider, ProviderError, StubProvider


ALLOWED_PROVIDERS = {"stub", "mock", "external"}


def build_provider(settings: LLMSettings) -> LLMProvider:
    """
    Allow-list provider factory (fail-closed).
    Invariants:
      - In record mode provider is required
      - Provider must be one of {stub, mock, external}
    """
    name = settings.provider
    if name is None:
        raise ProviderError("LLM_PROVIDER is required in LLM_MODE=record")

    if name not in ALLOWED_PROVIDERS:
        raise ProviderError(f"Unknown LLM_PROVIDER={name!r}. Allowed: {sorted(ALLOWED_PROVIDERS)}")

    if name == "stub":
        return StubProvider()
    if name == "mock":
        return MockProvider()
    if name == "external":
        return ExternalProvider()

    raise ProviderError(f"Unhandled provider: {name!r}")
