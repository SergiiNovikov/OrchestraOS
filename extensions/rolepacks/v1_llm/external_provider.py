from __future__ import annotations

from typing import Any, Dict, Mapping

from validation.schemas import SCHEMA_INTENT_PACKAGE_V0, validate_artifact_v0

from .fixture_schema_v1 import FixtureSchemaError, FixtureV1, parse_fixture_v1
from .fixtures import FixturesError, FixturesStore, read_fixtures_dir_from_env
from .provider import ProviderError, _allowed_contours, _extract_baseline_norm


class ExternalProvider:
    """
    "Real provider" skeleton without network:
      - reads fixture by stable_input_key
      - validates fixture schema v1 (fail-closed, stable errors)
      - normalizes/parses into intent_package_v0
      - validates schema (fail-closed)
    """

    def __init__(self) -> None:
        self._store = FixturesStore(fixtures_dir=read_fixtures_dir_from_env())

    def generate_intent(
        self,
        scoped_request_v0: Mapping[str, Any],
        stable_input_key: str,
        canonical_json: str,
    ) -> Dict[str, Any]:
        try:
            raw = self._store.read_fixture(stable_input_key)
        except FixturesError as e:
            raise ProviderError(str(e)) from e

        try:
            fx: FixtureV1 = parse_fixture_v1(raw)
        except FixtureSchemaError as e:
            raise ProviderError(f"Fixture schema invalid: {e}") from e

        identity = scoped_request_v0["identity"]
        fp = scoped_request_v0["input_fingerprint"]
        baseline_hash = fp["baseline_norm_hash"]

        baseline_norm = _extract_baseline_norm(scoped_request_v0)
        status = "RESOLVED" if baseline_norm.strip() else "AMBIGUOUS"

        intent_package: Dict[str, Any] = {
            "schema_version": SCHEMA_INTENT_PACKAGE_V0,
            "identity": {
                "envelope_id": identity["envelope_id"],
                "req_id": identity["req_id"],
                "trace_id": identity["trace_id"],
            },
            "source_fingerprint": {
                "baseline_norm_hash": baseline_hash,
            },
            "intent_definition": {
                "intent_status": status,
                "constraints": {
                    "allowed_contours": _allowed_contours(scoped_request_v0),
                    "required_by_contract": [],
                },
            },
            "ambiguity_report": {
                "ambiguous": status != "RESOLVED",
                "ambiguity_reason": ["empty baseline_norm"] if status != "RESOLVED" else None,
            },
            "conflict_report": {
                "conflicts_present": False,
                "conflict_summary": None,
            },
            "handoff": {
                "target_role": "task_decomposer",
                "notes_for_downstream": [],
            },
        }

        fields = fx.to_summary_fields()

        notes = [
            f"baseline_norm='{baseline_norm}'",
            f"v1_llm.provider='external'",
            f"fixture_schema_version='{fx.fixture_schema_version}'",
            f"v1_llm.kind='{fields['kind']}'",
            f"v1_llm.lang='{fields['lang']}'",
            f"v1_llm.tags={fields['tags']}",
            f"stable_input_key='{stable_input_key}'",
            f"canonical_intent_input_json='{canonical_json}'",
        ]
        notes.extend(fields["notes"])

        # Optional: keep raw_completion / parsed_intent out of notes (avoid huge strings),
        # but you can add markers if present.
        if fx.raw_completion is not None:
            notes.append("fixture.raw_completion_present=true")
        if fx.parsed_intent is not None:
            notes.append("fixture.parsed_intent_present=true")

        intent_package["handoff"]["notes_for_downstream"] = notes

        validate_artifact_v0(artifact=intent_package, expected_schema_version=SCHEMA_INTENT_PACKAGE_V0)
        return intent_package
