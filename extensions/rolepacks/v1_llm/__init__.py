from __future__ import annotations

# v1_llm rolepack package
#
# Install the canonical v0 validator shim early so any validate_artifact_v0() calls
# made within this rolepack don't crash due to missing artifacts modules in this repo snapshot.
from extensions.rolepacks.v1_tz._v0_validator_shim import ensure_v0_validators_importable

ensure_v0_validators_importable()
