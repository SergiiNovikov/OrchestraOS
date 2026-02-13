from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="front_cli",
        description="OrchestraOS Front Manager CLI Harness + Conversation Mode",
    )

    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", type=str, help="User input text (single run)")
    g.add_argument("--repl", action="store_true", help="Start REPL mode")
    g.add_argument("--new-conversation", action="store_true", help="Start a new conversation loop")
    g.add_argument("--conversation", type=str, help="Continue an existing conversation loop by id")

    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Profile name in extensions/profiles (without .json) or path to .json. Default: tz_cli_default",
    )

    # M18.1 Observability (read-only)
    parser.add_argument("--show-problem-model", action="store_true", help="Print problem_model_v1 and exit (read-only)")
    parser.add_argument(
        "--problem-model-format",
        type=str,
        choices=["short", "json"],
        default="short",
        help="Viewer output format",
    )
    return parser


def _run_problem_model_viewer(*, conversation_id: str, profile_arg: str | None, fmt: str) -> int:
    # Lazy imports: do NOT import apps.front_cli.main here (avoid coupling to conversation loop)
    from pathlib import Path

    from apps.front_cli.config import load_profile
    from extensions.conversation.state_store import load_state
    from extensions.cognitive.problem_model_v1 import default_problem_model, validate_problem_model_fail_closed
    from extensions.cognitive.viewer_v1 import format_problem_model_view

    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    work_dir = Path(str(prof.data["work_dir"]))
    try:
        state = load_state(conversation_id, work_dir)
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1

    pm = state.get("problem_model_v1")
    if not isinstance(pm, dict):
        pm = default_problem_model()

    # Fail-closed validation for viewer too
    try:
        validate_problem_model_fail_closed(pm)
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1

    view = format_problem_model_view(pm, style=fmt)
    sys.stdout.write(view.rstrip("\n") + "\n")
    sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # M18.1 viewer: only meaningful with existing conversation id
    if args.show_problem_model:
        if args.conversation is None:
            sys.stderr.write("[ERROR] --show-problem-model requires --conversation <id>\n")
            return 2
        return _run_problem_model_viewer(conversation_id=args.conversation, profile_arg=args.profile, fmt=args.problem_model_format)

    # Normal modes (lazy import main)
    from apps.front_cli.main import run_conversation_mode, run_repl_mode, run_text_mode

    if args.repl:
        return run_repl_mode(profile_arg=args.profile)

    if args.new_conversation:
        return run_conversation_mode(profile_arg=args.profile, new_conversation=True, conversation_id=None)

    if args.conversation is not None:
        return run_conversation_mode(profile_arg=args.profile, new_conversation=False, conversation_id=args.conversation)

    return run_text_mode(text=args.text, profile_arg=args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
