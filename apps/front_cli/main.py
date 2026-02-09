from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from runtime.runner import run_pipeline_v0

from apps.front_cli.adapters import (
    EnvelopeOnlyValidatorV0,
    build_request_envelope_from_text,
    environment_from_profile,
    ensure_specs_dir,
    minimal_specs_from_profile,
    roles_deterministic,
    validate_envelope_fail_closed,
)
from apps.front_cli.config import load_profile
from apps.front_cli.io import print_run_output, run_repl, save_run_artifacts


def _run_once(text: str, profile: Dict[str, Any]) -> Tuple[Any, Any, Dict[str, Any], str, Path]:
    # 1) build deterministic envelope
    env = build_request_envelope_from_text(text=text, profile=profile)

    # 2) validate envelope via v0 artifacts validator (fail-closed)
    validate_envelope_fail_closed(env)

    # 3) build wiring exactly like proven determinism harness
    specs_dir = Path(str(profile["specs_dir"]))
    ensure_specs_dir(specs_dir)

    environment = environment_from_profile(profile)
    roles = roles_deterministic()
    validator = EnvelopeOnlyValidatorV0()
    specs = minimal_specs_from_profile(profile)

    # 4) run v0 pipeline (canonical)
    out, err, manifest = run_pipeline_v0(
        primary_input=env,
        specs_dir=specs_dir,
        environment=environment,
        roles=roles,
        validator=validator,  # validates envelope at scope_resolver input only
        specs=specs,
    )

    manifest_dict = manifest.to_dict()
    trace_id = env["header"]["trace_id"]
    work_dir = Path(str(profile["work_dir"]))
    return out, err, manifest_dict, trace_id, work_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="front_cli", description="OrchestraOS Front Manager CLI Harness (Milestone 0)")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", type=str, help="User input text (single run)")
    g.add_argument("--repl", action="store_true", help="Start REPL mode")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Profile name in extensions/profiles (without .json) or path to .json. Default: tz_cli_default",
    )
    args = parser.parse_args(argv)

    try:
        prof = load_profile(args.profile)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    if args.repl:
        return run_repl(build_and_run=lambda t: _run_once(t, prof.data))

    try:
        out, err, m, trace_id, work_dir = _run_once(args.text, prof.data)  # type: ignore[arg-type]
        print_run_output(out, err, m)
        save_run_artifacts(work_dir=work_dir, trace_id=trace_id, out=out, err=err, manifest_dict=m)

        # Fail-closed contract: runtime_error -> non-zero exit
        return 0 if err is None else 1
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
