from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, List, Optional


def _dump_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        return repr(obj)


def _extract_output_summary(out: Any) -> Dict[str, Any]:
    """
    Best-effort summary for the deterministic rolepack output shape:
      {"stage": "...", "in": <prev>}
    We DO NOT assume v0 schemas here; only heuristics for nicer CLI UX.
    """
    stages: List[str] = []
    cur = out
    baseline_norm: Optional[str] = None
    trace_id: Optional[str] = None

    # walk down the nested {"stage","in"} chain
    for _ in range(32):  # hard stop to avoid infinite loops
        if not isinstance(cur, dict):
            break

        stage = cur.get("stage")
        if isinstance(stage, str):
            stages.append(stage)

        inner = cur.get("in")
        if inner is None:
            # Try to extract from the leaf (which is request_envelope_v0 in our Milestone 0)
            payload_iso = cur.get("payload_isolation")
            if isinstance(payload_iso, dict):
                bn = payload_iso.get("baseline_norm")
                if isinstance(bn, str):
                    baseline_norm = bn

            hdr = cur.get("header")
            if isinstance(hdr, dict):
                tid = hdr.get("trace_id")
                if isinstance(tid, str):
                    trace_id = tid
            break

        cur = inner

    # Also try to extract baseline_norm/trace_id from the final leaf if it is request_envelope-like
    if isinstance(cur, dict):
        payload_iso = cur.get("payload_isolation")
        if isinstance(payload_iso, dict):
            bn = payload_iso.get("baseline_norm")
            if isinstance(bn, str):
                baseline_norm = bn
        hdr = cur.get("header")
        if isinstance(hdr, dict):
            tid = hdr.get("trace_id")
            if isinstance(tid, str):
                trace_id = tid

    return {
        "stages": stages[::-1] if stages else [],  # reverse to show scope_resolver..result_assembler
        "trace_id": trace_id,
        "baseline_norm": baseline_norm,
    }


def print_run_output(out: Any, err: Any, manifest_dict: Dict[str, Any]) -> None:
    # Extra compact summary (does not change semantics)
    summary = _extract_output_summary(out)
    sys.stdout.write("=== output_summary ===\n")
    sys.stdout.write(_dump_json(summary) + "\n\n")

    sys.stdout.write("=== output ===\n")
    sys.stdout.write(_dump_json(out) + "\n")
    sys.stdout.write("\n=== runtime_error ===\n")
    sys.stdout.write(_dump_json(err) + "\n")
    sys.stdout.write("\n=== run_manifest ===\n")
    sys.stdout.write(_dump_json(manifest_dict) + "\n")
    sys.stdout.flush()


def save_run_artifacts(*, work_dir: Path, trace_id: str, out: Any, err: Any, manifest_dict: Dict[str, Any]) -> None:
    """
    Runner v0 сам не пишет файлы, поэтому сохраняем только “sidecar json” в work_dir.
    Это НЕ новый артефакт протокола, просто удобный вывод.
    Fail-closed: любые ошибки записи -> исключение.
    """
    run_dir = work_dir / "runs" / trace_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "run_manifest.json").write_text(_dump_json(manifest_dict), encoding="utf-8")

    if err is None:
        (run_dir / "output.json").write_text(_dump_json(out), encoding="utf-8")
    else:
        (run_dir / "runtime_error.json").write_text(_dump_json(err), encoding="utf-8")


def run_repl(*, build_and_run: Callable[[str], Tuple[Any, Any, Dict[str, Any], str, Path]]) -> int:
    """
    REPL: per-turn errors printed to stderr; session continues.
    build_and_run returns: (out, err, manifest_dict, trace_id, work_dir)
    """
    sys.stdout.write("OrchestraOS Front CLI REPL. Type 'exit' or Ctrl-D to quit.\n")
    sys.stdout.flush()

    while True:
        try:
            line = input("orchestra> ")
        except EOFError:
            # POSIX shells typically raise EOFError on Ctrl-D
            sys.stdout.write("\n")
            return 0

        text = line.strip()

        # Windows/PowerShell: Ctrl-D can arrive as literal \x04 (not EOF).
        if text in {"\x04", "\u0004"}:
            sys.stdout.write("\n")
            return 0

        # Strip stray control-D if mixed with other chars.
        if "\x04" in text:
            text = text.replace("\x04", "").strip()

        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            return 0

        try:
            out, err, m, trace_id, work_dir = build_and_run(text)
            print_run_output(out, err, m)
            save_run_artifacts(work_dir=work_dir, trace_id=trace_id, out=out, err=err, manifest_dict=m)
        except Exception as e:
            sys.stderr.write(f"[ERROR] {e}\n")
            sys.stderr.flush()
            continue
