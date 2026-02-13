from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from extensions.rolepacks.v1_llm.fixtures import default_fixtures_dir
from extensions.rolepacks.v1_llm.stable_key import canonical_intent_input_json, stable_input_key


def _sha256_hex(s: str) -> str:
    import hashlib

    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _build_min_scoped_request_for_key(text: str) -> Dict[str, Any]:
    return {
        "schema_version": "scoped_request_v0",
        "identity": {"envelope_id": "env_tool", "req_id": "req_tool", "trace_id": "trace_tool"},
        "input_fingerprint": {"baseline_norm_hash": _sha256_hex(text)},
        "scope": {"allowed_contours": ["text"]},
        "handoff": {"handoff_payload": {"baseline_norm": text}},
    }


def _template_fixture_payload_v1() -> Dict[str, Any]:
    # Fixture schema v1 (validated by ExternalProvider)
    return {
        "fixture_schema_version": "fixture_schema_v1",
        "kind": "generic",
        "lang": "unknown",
        "tags": [],
        "notes": [],
        "raw_completion": "<paste model output here>",
        "parsed_intent": {
            "kind": "generic",
            "lang": "unknown",
            "tags": [],
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate stable_input_key and fixture path for v1_llm external provider.")
    p.add_argument("--text", required=True, help="Input text (baseline_norm).")
    p.add_argument(
        "--fixtures-dir",
        default=None,
        help="Override fixtures directory (default: tests_ext/_llm_fixtures/).",
    )
    p.add_argument(
        "--write-template",
        action="store_true",
        help="Write a JSON template fixture at the computed path (fail if already exists).",
    )
    args = p.parse_args(argv)

    text: str = args.text

    sr = _build_min_scoped_request_for_key(text)
    key = stable_input_key(sr)
    canon_json = canonical_intent_input_json(sr)

    fixtures_dir = Path(args.fixtures_dir) if args.fixtures_dir else default_fixtures_dir()
    fixture_path = fixtures_dir / f"{key}.json"

    out = {
        "stable_input_key": key,
        "canonical_intent_input_json": canon_json,
        "baseline_norm_hash": sr["input_fingerprint"]["baseline_norm_hash"],
        "fixture_path": str(fixture_path),
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))

    if args.write_template:
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        if fixture_path.exists():
            raise SystemExit(f"Refusing to overwrite existing fixture: {fixture_path}")

        payload = _template_fixture_payload_v1()
        fixture_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote template fixture: {fixture_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
